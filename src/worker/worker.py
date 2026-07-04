import asyncio
import logging
from typing import Any
from uuid import UUID

from src.entities.enums.generation_status import GenerationStatus
from src.providers.classes.nano_banana import NanoBanana
from src.providers.interfaces.Iredis_cache import IRedisCache
from src.providers.interfaces.IseaweedFS import ISeaweedFS
from src.repositories.interfaces.Icost_ledger_repository import ICostLedgerRepository
from src.repositories.interfaces.Igeneration_product_repository import (
    IGenerationProductRepository,
)
from src.repositories.interfaces.Igeneration_repository import IGenerationRepository
from src.repositories.interfaces.Iproduct_repository import IProductRepository
from src.worker.handler.image_loader import ImageLoader

logger = logging.getLogger(__name__)

_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/bmp": "bmp",
}

_GEN_STATUS_TTL = 1800  # 1h — ventana para SSE late-join


def _status_key(idem_key: str) -> str:
    return f"gen_status:{idem_key}"


def _channel(idem_key: str) -> str:
    return f"generation:{idem_key}"


class Worker:
    """Procesa un payload de generación — pipeline completo.

    Semáforo = 1: sólo una ejecución activa a la vez.
    El scheduler llama a ``process()`` que adquiere el semáforo (bloqueante si
    el worker está ocupado) y retorna cuando termina, sea éxito o error.

    Pipeline:
      1. Crear registro Generation (PENDING)
      2. Vincular productos de referencia (GenerationProduct)
      3. Transicionar status → PROCESSING
      4. Cargar imágenes en memoria (input + referencias vía ImageLoader)
      5. Llamar a NanoBanana.generate()
      6. Subir imagen generada a SeaweedFS
      7. Actualizar Generation (COMPLETED + output_image_path)
      8. Registrar costos en CostLedger vía invoice

    En caso de error en pasos 4-8 → status FAILED.
    """

    def __init__(
        self,
        generation_repository: IGenerationRepository,
        generation_product_repository: IGenerationProductRepository,
        product_repository: IProductRepository,
        cost_ledger_repository: ICostLedgerRepository,
        nano_banana: NanoBanana,
        seaweed_fs: ISeaweedFS,
        redis_cache: IRedisCache,
    ) -> None:
        self._generation_repo = generation_repository
        self._generation_product_repo = generation_product_repository
        self._product_repo = product_repository
        self._cost_ledger_repo = cost_ledger_repository
        self._nano_banana = nano_banana
        self._seaweed_fs = seaweed_fs
        self._redis = redis_cache
        self._image_loader = ImageLoader(seaweed_fs, redis_cache)
        self._semaphore = asyncio.Semaphore(1)

    async def process(self, payload: dict[str, Any]) -> bool:
        async with self._semaphore:
            return await self._execute(payload)

    async def _execute(self, payload: dict[str, Any]) -> bool:
        idem_key: str = payload.get("idem_key", "unknown")
        manager_id = UUID(payload["manager_id"])
        store_id = UUID(payload["store_id"])
        prompt: str = payload.get("prompt", "")
        model: str = payload.get("model", "google/gemini-3.1-flash-image-preview")
        req_type: str = payload.get("req_type", "abierto")
        referencias: list[str] = payload.get("referencias", [])
        input_image_path: str | None = payload.get("input_image_path")

        logger.info(
            "Worker executing — idem_key=%s model=%s req_type=%s refs=%d",
            idem_key, model, req_type, len(referencias),
        )

        # ── 1. Crear Generation ──────────────────────────────────
        generation = await self._generation_repo.create(
            manager_id=manager_id,
            store_id=store_id,
            prompt=prompt,
            input_image_path=input_image_path,
        )
        if generation is None:
            logger.error("Worker failed — create Generation (idem_key=%s)", idem_key)
            return False

        gen_id = generation.id
        logger.info("Generation created — id=%s idem_key=%s", gen_id, idem_key)

        # ── 2. Vincular productos de referencia ──────────────────
        for ref in referencias:
            ok = await self._generation_product_repo.create(
                generation_id=gen_id, product_id=UUID(ref),
            )
            if not ok:
                logger.warning("Link GenerationProduct failed — gen=%s product=%s", gen_id, ref)

        # ── 3. Status → PROCESSING ───────────────────────────────
        await self._generation_repo.update(gen_id, status=GenerationStatus.PROCESSING)
        await self._notify(idem_key, gen_id, "processing")
        logger.info("Generation status → PROCESSING — id=%s", gen_id)

        try:
            # ── 4. Cargar imágenes en memoria ───────────────────
            images: list[bytes] = []

            if req_type == "abierto" and input_image_path:
                logger.info("Loading input image — path=%s", input_image_path)
                input_img = await self._image_loader.load(
                    bucket="input_images", file_path=input_image_path,
                )
                images.append(input_img)

            if referencias:
                ref_uuids = [UUID(ref) for ref in referencias]
                url_map = await self._product_repo.find_image_urls_by_ids(ref_uuids)

                for ref_uuid in ref_uuids:
                    image_url = url_map.get(ref_uuid)
                    if image_url is None:
                        logger.warning(
                            "Reference product missing or no image_url — uuid=%s", ref_uuid
                        )
                        continue

                    ref_img = await self._image_loader.load(
                        bucket="products", file_path=image_url,
                    )
                    images.append(ref_img)

            logger.info("Images loaded — total=%d", len(images))

            if not images:
                raise RuntimeError("No images to process — check input_image and references")

            # ── 5. Llamar a NanoBanana ───────────────────────────
            generated, invoice = await self._nano_banana.generate(
                prompt=prompt,
                images=images,
                model=model,
            )
            logger.info(
                "Generation complete — images=%d tokens=%d cost=%.6f",
                len(generated), invoice.tokens, invoice.amount,
            )

            # ── 6. Subir resultado a SeaweedFS ───────────────────
            output_path: str | None = None
            if generated:
                gen_img = generated[0]
                ext = _MIME_TO_EXT.get(gen_img.mime_type, "png")
                output_path = self._seaweed_fs.upload_file(
                    file_bytes=gen_img.data,
                    file_name=f"{gen_id}.{ext}",
                    content_type=gen_img.mime_type,
                    bucket="output",
                    # prefix="output",
                )
                logger.info("Output uploaded — path=%s", output_path)

            # ── 7. Actualizar Generation → COMPLETED ─────────────
            await self._generation_repo.update(
                gen_id,
                status=GenerationStatus.COMPLETED,
                output_image_path=output_path,
            )
            await self._notify(idem_key, gen_id, "completed", output_path=output_path)
            logger.info("Generation status → COMPLETED — id=%s", gen_id)

            # ── 8. Registrar costos ──────────────────────────────
            await self._cost_ledger_repo.create(
                manager_id=manager_id,
                store_id=store_id,
                generation_id=gen_id,
                amount=invoice.amount,
                currency=invoice.currency,
                provider=invoice.provider,
                model=invoice.model,
                tokens=invoice.tokens,
                description=invoice.description,
            )
            logger.info("Cost recorded — gen_id=%s amount=%.6f", gen_id, invoice.amount)

            logger.info("Worker completed — idem_key=%s gen_id=%s", idem_key, gen_id)
            return True

        except Exception as e:
            logger.error("Worker pipeline error — idem_key=%s: %s", idem_key, e, exc_info=True)
            await self._generation_repo.update(gen_id, status=GenerationStatus.FAILED)
            await self._notify(idem_key, gen_id, "failed", error=str(e))
            logger.info("Generation status → FAILED — id=%s", gen_id)
            return False

    # ------------------------------------------------------------------
    async def _notify(
        self,
        idem_key: str,
        gen_id: UUID,
        step: str,
        *,
        output_path: str | None = None,
        error: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "step": step,
            "idem_key": idem_key,
            "generation_id": str(gen_id),
        }
        if output_path is not None:
            payload["output_path"] = output_path
        if error is not None:
            payload["error"] = error

        # persistir último estado para SSE late-join (TTL 1h)
        await self._redis.set(
            key=_status_key(idem_key),
            value=self._redis._serialize_payload(payload),
            ttl=_GEN_STATUS_TTL,
        )
        # broadcast en tiempo real
        await self._redis.publish(_channel(idem_key), payload)

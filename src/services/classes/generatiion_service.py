import logging
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile

from src.dto.generation_dtos import CreateGenerationDTO, GenerationType
from src.helpers.rate_limit import RateLimiter
from src.mappers.response_mappers import to_bad_request_response
from src.providers.interfaces.Iredis_cache import IRedisCache
from src.providers.interfaces.IseaweedFS import ISeaweedFS
from src.repositories.interfaces.Imanager_repository import IManagerRepository
from src.services.interfaces.Igeneratiion_service import IGenerationService
from src.utils.image_content_type import get_content_type_from_filename
from src.utils.image_extension import validate_image_extension
from src.utils.image_size import validate_image_size

logger = logging.getLogger(__name__)


class GenerationService(IGenerationService):
    def __init__(
        self,
        manager_repository: IManagerRepository,
        rate_limiter: RateLimiter,
        seaweed_fs: ISeaweedFS,
        redis_cache: IRedisCache,
    ):
        self._manager_repository = manager_repository
        self._rate_limiter = rate_limiter
        self._seaweed_fs = seaweed_fs
        self._redis_cache = redis_cache

    async def create(
        self,
        *,
        dto: CreateGenerationDTO,
        image: Optional[UploadFile] = None,
    ) -> dict[str, Any]:
        logger.info(
            "Creating generation — manager_key=%s req_type=%s model=%s refs=%d",
            dto.manager_key, dto.req_type.value, dto.model, len(dto.referencias),
        )

        # ── 1. Authorize manager + rate limit ──────────────────────
        manager_data = await self._rate_limiter.get_cached_manager(dto.manager_key)

        if manager_data is None:
            logger.info("Manager %s not cached, looking up in DB", dto.manager_key)
            manager = await self._manager_repository.find_by_key(dto.manager_key)
            if manager is None:
                logger.warning("Manager %s not found in DB", dto.manager_key)
                err = to_bad_request_response(
                    message="Manager no encontrado",
                    error_code="MANAGER_NOT_FOUND",
                    details=[{
                        "property": "manager_key",
                        "constraints": f"No existe un manager con la key '{dto.manager_key}'",
                    }],
                )
                raise HTTPException(status_code=400, detail=err.model_dump())

            manager_data = {
                "manager_id": str(manager.id),
                "store_id": str(manager.store_id),
            }
            logger.info("Manager %s found — caching and charging tokens", dto.manager_key)
            manager_data = await self._rate_limiter.authorize_and_charge(
                dto.manager_key, dto.model, manager_data=manager_data,
            )
        else:
            logger.info("Manager %s cached — charging tokens", dto.manager_key)
            manager_data = await self._rate_limiter.authorize_and_charge(
                dto.manager_key, dto.model,
            )

        logger.info(
            "Manager authorized — manager_id=%s store_id=%s",
            manager_data["manager_id"], manager_data["store_id"],
        )

        # ── 2. Validate & upload image ────────────────────────────
        input_image_path: str | None = None

        if dto.req_type == GenerationType.DETERMINISTA and image is not None:
            logger.warning(
                "Determinista request with image rejected — filename=%s", image.filename,
            )
            err = to_bad_request_response(
                message="Imagen no permitida",
                error_code="VALIDATION_ERROR",
                details=[{
                    "property": "image",
                    "constraints": "No puede enviarse una imagen cuando el tipo de generación es 'determinista'",
                    "value": image.filename,
                }],
            )
            raise HTTPException(status_code=400, detail=err.model_dump())

        if image and image.filename:
            logger.info("Validating image — filename=%s", image.filename)
            try:
                validate_image_extension(image.filename)
                await validate_image_size(image)
            except ValueError as e:
                logger.warning("Image validation failed — %s", e)
                err = to_bad_request_response(
                    message="Error de validación de imagen",
                    error_code="VALIDATION_ERROR",
                    details=[{
                        "property": "image",
                        "constraints": str(e),
                        "value": image.filename,
                    }],
                )
                raise HTTPException(status_code=400, detail=err.model_dump())

            content_type = get_content_type_from_filename(image.filename)
            file_bytes = await image.read()

            input_image_path = self._seaweed_fs.upload_file(
                file_bytes=file_bytes,
                file_name=image.filename,
                content_type=content_type,
                bucket="input_images",
                # prefix="input_images",
            )
            logger.info("Image uploaded to SeaweedFS — path=%s", input_image_path)
        else:
            logger.info("No image provided — proceeding without")

        # ── 3. Build payload & enqueue ────────────────────────────
        idem_key = str(uuid4())

        payload: dict[str, Any] = {
            "idem_key": idem_key,
            "manager_id": manager_data["manager_id"],
            "store_id": manager_data["store_id"],
            "prompt": dto.prompt,
            "req_type": dto.req_type.value,
            "model": dto.model,
            "referencias": [str(ref) for ref in dto.referencias],
        }

        if input_image_path is not None:
            payload["input_image_path"] = input_image_path

        queue_len = await self._redis_cache.enqueue(
            manager_id=manager_data["manager_id"],
            payload=payload,
        )
        logger.info(
            "Payload enqueued — idem_key=%s manager_id=%s queue_size=%d",
            idem_key, manager_data["manager_id"], queue_len,
        )

        logger.info("Generation request accepted — idem_key=%s", idem_key)
        return {"idem_key": idem_key, "state": "process"}


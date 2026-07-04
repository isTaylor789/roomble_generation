import asyncio
import logging

from src.providers.interfaces.Iredis_cache import IRedisCache
from src.worker.worker import Worker

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5  # cada cuánto revisar Redis cuando no hay nada pendiente


class Scheduler:
    """Scheduler que monitorea colas FIFO en Redis y delega al Worker.

    Ciclo:
      1. Descubre todos los manager_id con cola en Redis via SCAN.
      2. Por cada cola, si hay elementos encolados, popula el primero (FIFO).
      3. Lo pasa al Worker (semáforo=1 → espera si ocupado).
      4. Cuando el Worker termina (éxito o error), el elemento ya fue eliminado.
      5. Pasa al siguiente elemento inmediatamente; si no hay, espera y repite.
    """

    def __init__(
        self,
        redis_cache: IRedisCache,
        worker: Worker,
    ) -> None:
        self._redis = redis_cache
        self._worker = worker
        self._running = False

    async def run(self) -> None:
        """Loop principal — corre hasta que se llame a ``stop()``."""
        self._running = True
        logger.info("Scheduler started — poll interval=%ds", POLL_INTERVAL_SECONDS)

        while self._running:
            try:
                processed = await self._tick()
                if not processed:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
            except Exception as e:
                logger.error("Scheduler tick error: %s", e, exc_info=True)
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _tick(self) -> bool:
        """Revisa colas en Redis y procesa el primer elemento FIFO.

        Returns:
            ``True`` si se procesó al menos un elemento,
            ``False`` si no había nada pendiente.
        """
        raw = self._redis._client  # RedisCache expone el cliente raw
        cursor = 0
        manager_ids: list[str] = []
        while True:
            cursor, keys = await raw.scan(cursor=cursor, match="queue:manager:*", count=100)
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                manager_ids.append(key_str.split(":", 2)[-1])
            if cursor == 0:
                break

        for manager_id in manager_ids:
            queue_len = await self._redis.queue_length(manager_id=manager_id)

            if queue_len == 0:
                continue

            # ── Pop atómico (FIFO) ────────────────────────────────
            payload = await self._redis.delete_top(manager_id=manager_id)
            if payload is None:
                continue  # alguien más se nos adelantó

            idem_key = payload.get("idem_key", "unknown")
            logger.info(
                "Dispatching payload — manager_id=%s idem_key=%s queue_left=%d",
                manager_id, idem_key, queue_len - 1,
            )

            # ── Procesar (bloqueante: espera si worker ocupado) ───
            success = await self._worker.process(payload)

            logger.info(
                "Payload finished — idem_key=%s success=%s",
                idem_key, success,
            )

            # El payload ya fue eliminado de la cola via delete_top.
            # Inmediatamente revisamos el siguiente (no esperamos).
            return True

        return False

    async def stop(self) -> None:
        """Detiene el scheduler de forma segura."""
        self._running = False
        logger.info("Scheduler stopping")

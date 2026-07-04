import json
from typing import Any, AsyncGenerator
from redis.asyncio import Redis

from src.providers.interfaces.Iredis_cache import IRedisCache


class RedisCache(IRedisCache):
    def __init__(self, host: str, port: int, password: str | None = None):
        self._client = Redis(
            host=host,
            port=port,
            password=password or None,
            decode_responses=False,  # queremos bytes para imágenes y payloads
        )

    async def set(self, *, key: str, value: bytes, ttl: int) -> None:
        await self._client.set(key, value, ex=ttl)

    async def get(self, key: str) -> bytes | None:
        return await self._client.get(key)

    def _queue_key(self, manager_id: str) -> str:
        return f"queue:manager:{manager_id}"

    def _serialize_payload(self, payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def _deserialize_payload(self, raw: bytes) -> dict[str, Any]:
        return json.loads(raw.decode("utf-8"))

    async def publish(self, channel: str, message: dict[str, Any]) -> int:
        raw = self._serialize_payload(message)
        return await self._client.publish(channel, raw)

    async def subscribe(self, channel: str) -> AsyncGenerator[dict[str, Any], None]:
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    yield self._deserialize_payload(msg["data"])
        finally:
            await pubsub.unsubscribe(channel)

    async def enqueue(self, *, manager_id: str, payload: dict[str, Any]) -> int:
        """
        Mete el payload al final de la cola FIFO del manager.
        Retorna la longitud de la cola después del push.
        """
        queue_key = self._queue_key(manager_id)
        raw_payload = self._serialize_payload(payload)
        return await self._client.rpush(queue_key, raw_payload)

    async def peek_top(self, *, manager_id: str) -> dict[str, Any] | None:
        """
        Ve el primer elemento sin borrarlo.
        """
        queue_key = self._queue_key(manager_id)
        raw_payload = await self._client.lindex(queue_key, 0)

        if raw_payload is None:
            return None

        return self._deserialize_payload(raw_payload)

    async def list_top(
        self, *, manager_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Lista los primeros N elementos, del más antiguo al más nuevo.
        """
        if limit <= 0:
            return []

        queue_key = self._queue_key(manager_id)
        raw_payloads = await self._client.lrange(queue_key, 0, limit - 1)

        return [self._deserialize_payload(item) for item in raw_payloads]

    async def delete_top(self, *, manager_id: str) -> dict[str, Any] | None:
        """
        Elimina el primer elemento de la cola y lo retorna.
        Ojo: no toca nada dentro del payload, incluido manager_id.
        """
        queue_key = self._queue_key(manager_id)
        raw_payload = await self._client.lpop(queue_key)

        if raw_payload is None:
            return None

        return self._deserialize_payload(raw_payload)

    async def queue_length(self, *, manager_id: str) -> int:
        """
        Retorna el tamaño actual de la cola del manager.
        """
        queue_key = self._queue_key(manager_id)
        return await self._client.llen(queue_key)
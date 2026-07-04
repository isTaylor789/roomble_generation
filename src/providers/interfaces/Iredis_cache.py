from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator


class IRedisCache(ABC):
    @abstractmethod
    async def set(self, *, key: str, value: bytes, ttl: int) -> None:
        """Guarda un valor en Redis con TTL en segundos."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Obtiene un valor de Redis. Retorna None si no existe o expiró."""
        raise NotImplementedError

    @abstractmethod
    async def enqueue(self, *, manager_id: str, payload: dict[str, Any]) -> int:
        """Encola un payload al final de la cola FIFO del manager."""
        raise NotImplementedError

    @abstractmethod
    async def peek_top(self, *, manager_id: str) -> dict[str, Any] | None:
        """Retorna el primer elemento de la cola sin eliminarlo."""
        raise NotImplementedError

    @abstractmethod
    async def list_top(
        self, *, manager_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Lista los primeros N elementos, del más antiguo al más nuevo."""
        raise NotImplementedError

    @abstractmethod
    async def delete_top(self, *, manager_id: str) -> dict[str, Any] | None:
        """Elimina el primer elemento de la cola y lo retorna."""
        raise NotImplementedError

    @abstractmethod
    async def queue_length(self, *, manager_id: str) -> int:
        """Retorna el tamaño actual de la cola del manager."""
        raise NotImplementedError

    @abstractmethod
    async def publish(self, channel: str, message: dict[str, Any]) -> int:
        """Publica un mensaje JSON en un canal PubSub. Retorna número de suscriptores."""
        raise NotImplementedError

    @abstractmethod
    async def subscribe(self, channel: str) -> AsyncGenerator[dict[str, Any], None]:
        """Suscribe a un canal PubSub. Yield dicts parseados de JSON."""
        raise NotImplementedError
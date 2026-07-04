from typing import Optional, Protocol
from uuid import UUID


class ICostLedgerRepository(Protocol):
    async def create(
        self,
        *,
        manager_id: UUID,
        store_id: UUID,
        generation_id: Optional[UUID] = None,
        amount: float,
        currency: str = "USD",
        description: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        tokens: Optional[int] = None,
    ) -> bool:
        ...

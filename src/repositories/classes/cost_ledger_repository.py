from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.entities.cost_ledger import CostLedger
from src.repositories.interfaces.Icost_ledger_repository import ICostLedgerRepository


class CostLedgerRepository(ICostLedgerRepository):
    def __init__(self, session_factory):
        self._session_factory = session_factory

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
        async with self._session_factory() as session:  # type: AsyncSession
            try:
                entry = CostLedger(
                    manager_id=manager_id,
                    store_id=store_id,
                    generation_id=generation_id,
                    amount=amount,
                    currency=currency,
                    description=description,
                    provider=provider,
                    model=model,
                    tokens=tokens,
                )
                session.add(entry)
                await session.commit()
                return True
            except Exception:
                await session.rollback()
                return False

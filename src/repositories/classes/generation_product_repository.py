from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.entities.generation_product import GenerationProduct
from src.repositories.interfaces.Igeneration_product_repository import (
    IGenerationProductRepository,
)


class GenerationProductRepository(IGenerationProductRepository):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def create(
        self,
        *,
        generation_id: UUID,
        product_id: UUID,
    ) -> bool:
        async with self._session_factory() as session:  # type: AsyncSession
            try:
                link = GenerationProduct(
                    generation_id=generation_id,
                    product_id=product_id,
                )
                session.add(link)
                await session.commit()
                return True
            except Exception:
                await session.rollback()
                return False

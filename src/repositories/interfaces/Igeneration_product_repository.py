from typing import Protocol
from uuid import UUID


class IGenerationProductRepository(Protocol):
    async def create(
        self,
        *,
        generation_id: UUID,
        product_id: UUID,
    ) -> bool:
        ...

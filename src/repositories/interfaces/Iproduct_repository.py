from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from src.entities.product import Product


class IProductRepository(Protocol):
    async def find_by_id(self, product_id: UUID) -> Product | None:
        ...

    async def find_image_urls_by_ids(self, product_ids: list[UUID]) -> dict[UUID, str | None]:
        """Retorna {product_id: image_url | None} solo para los IDs que existen."""
        ...
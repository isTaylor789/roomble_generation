from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.entities.product import Product
from src.helpers.pagination_template import build_pagination_meta
from src.repositories.interfaces.Iproduct_repository import IProductRepository


class ProductRepository(IProductRepository):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def find_by_id(self, product_id: UUID) -> Product | None:
        async with self._session_factory() as session:  # type AsyncSession
            stmt = select(Product).where(Product.id == product_id)
            result = await session.execute(stmt)

            if result is None:
                raise ValueError("No se pudo obtener el registro del producto")

            return result.scalar_one_or_none()

    async def find_image_urls_by_ids(self, product_ids: list[UUID]) -> dict[UUID, str | None]:
        if not product_ids:
            return {}

        async with self._session_factory() as session:  # type AsyncSession
            stmt = select(Product.id, Product.image_url).where(Product.id.in_(product_ids))
            result = await session.execute(stmt)
            rows = result.all()
            return {row[0]: row[1] for row in rows}

  
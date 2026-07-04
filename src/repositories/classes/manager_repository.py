from typing import Dict, List
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.entities.manager import Manager
from src.helpers.pagination_template import build_pagination_meta
from src.repositories.interfaces.Imanager_repository import IManagerRepository


class ManagerRepository(IManagerRepository):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def find_by_key(self, key: str) -> Manager | None:
        async with self._session_factory() as session:
            stmt = select(Manager).where(Manager.key == key)
            result = await session.execute(stmt)

            if result is None:
                raise ValueError(f"Error al buscar manager por key: {key}")
            
            return result.scalar_one_or_none()
from typing import Optional
from uuid import UUID

from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from src.entities.enums.generation_status import GenerationStatus
from src.entities.generation import Generation
from src.repositories.interfaces.Igeneration_repository import IGenerationRepository


class GenerationRepository(IGenerationRepository):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def create(
        self,
        *,
        manager_id: UUID,
        store_id: UUID,
        prompt: Optional[str] = None,
        input_image_path: Optional[str] = None,
        output_image_path: Optional[str] = None,
    ) -> Generation | None:
        async with self._session_factory() as session:  # type AsyncSession
            try:
                generation = Generation(
                    manager_id=manager_id,
                    store_id=store_id,
                    prompt=prompt,
                    input_image_path=input_image_path,
                    output_image_path=output_image_path,
                )
                session.add(generation)
                await session.commit()
                await session.refresh(generation)

                if not generation.id:
                    return None

                return generation
            except Exception:
                await session.rollback()
                return None

    async def update(
        self,
        generation_id: UUID,
        *,
        status: Optional[GenerationStatus] = None,
        output_image_path: Optional[str] = None,
    ) -> bool:
        values: dict = {}
        if status is not None:
            values["status"] = status
        if output_image_path is not None:
            values["output_image_path"] = output_image_path
        if not values:
            return False

        async with self._session_factory() as session:  # type AsyncSession
            try:
                stmt = sa_update(Generation).where(Generation.id == generation_id).values(**values)
                await session.execute(stmt)
                await session.commit()
                return True
            except Exception:
                await session.rollback()
                return False

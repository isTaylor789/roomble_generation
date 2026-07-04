from typing import Optional, Protocol
from uuid import UUID

from src.entities.enums.generation_status import GenerationStatus
from src.entities.generation import Generation


class IGenerationRepository(Protocol):
    async def create(
        self,
        *,
        manager_id: UUID,
        store_id: UUID,
        prompt: Optional[str] = None,
        input_image_path: Optional[str] = None,
        output_image_path: Optional[str] = None,
    ) -> Generation | None:
        ...

    async def update(
        self,
        generation_id: UUID,
        *,
        status: Optional[GenerationStatus] = None,
        output_image_path: Optional[str] = None,
    ) -> bool:
        ...

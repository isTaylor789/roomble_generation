from typing import Any, Optional, Protocol

from fastapi import UploadFile

from src.dto.generation_dtos import CreateGenerationDTO


class IGenerationService(Protocol):
    async def create(
        self,
        *,
        dto: CreateGenerationDTO,
        image: Optional[UploadFile] = None,
    ) -> dict[str, Any]:
        ...
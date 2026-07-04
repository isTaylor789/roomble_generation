from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class GenerationType(str, Enum):
    DETERMINISTA = "determinista"
    ABIERTO = "abierto"


class CreateGenerationDTO(BaseModel):
    manager_key: str = Field(
        ..., min_length=1, max_length=30,
        description="Clave única del manager que solicita la generación",
    )
    prompt: str = Field(
        ..., min_length=1,
        description="Prompt descriptivo para la generación",
    )
    req_type: GenerationType = Field(
        ...,
        description="Tipo de generación: 'determinista' (sin imagen) o 'abierto' (puede incluir imagen)",
    )
    model: str = Field(
        ..., min_length=1,
        description="Identificador del modelo de IA a usar",
    )
    referencias: list[UUID] = Field(
        ..., min_length=1,
        description="Lista de UUIDs de productos de referencia para la generación",
    )

    @field_validator("referencias")
    @classmethod
    def validate_referencias_not_empty(cls, v: list[UUID]) -> list[UUID]:
        if not v:
            raise ValueError("Debe proporcionar al menos una referencia")
        return v

    @field_validator("prompt")
    @classmethod
    def validate_prompt_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("El prompt no puede estar vacío")
        return v


class GenerationResponseDTO(BaseModel):
    id: UUID
    manager_id: UUID
    store_id: UUID
    status: str
    prompt: Optional[str] = None
    input_image_path: Optional[str] = None
    output_image_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

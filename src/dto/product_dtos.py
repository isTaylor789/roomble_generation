from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────── INPUT DTOs ────────────────────────────────

class CreateProductDTO(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=250,
        description="Nombre del producto (máx. 250 caracteres)",
    )
    category_id: UUID = Field(
        ..., description="UUID de la categoría a la que pertenece el producto",
    )
    description: Optional[str] = Field(
        None, description="Descripción del producto (máx. 400 palabras)",
    )

    @field_validator("description")
    @classmethod
    def validate_description_words(cls, v: str | None) -> str | None:
        if v is not None:
            word_count = len(v.split())
            if word_count > 400:
                raise ValueError(
                    f"La descripción excede el límite de 400 palabras (tiene {word_count})"
                )
        return v


class ProductIdDTO(BaseModel):
    id: UUID = Field(..., description="UUID del producto a consultar")


class UpdateProductDTO(BaseModel):
    name: Optional[str] = Field(
        None, min_length=1, max_length=250,
        description="Nuevo nombre del producto (máx. 250 caracteres)",
    )
    description: Optional[str] = Field(
        None, description="Nueva descripción del producto (máx. 400 palabras)",
    )
    is_available: Optional[bool] = Field(
        None, description="Disponibilidad del producto",
    )

    @field_validator("description")
    @classmethod
    def validate_description_words(cls, v: str | None) -> str | None:
        if v is not None:
            word_count = len(v.split())
            if word_count > 400:
                raise ValueError(
                    f"La descripción excede el límite de 400 palabras (tiene {word_count})"
                )
        return v

    @field_validator("name", "description", "is_available")
    @classmethod
    def validate_at_least_one(cls, v, info):
        return v

    def model_post_init(self, __context):
        if self.name is None and self.description is None and self.is_available is None:
            raise ValueError("Debe enviarse al menos un campo para actualizar (name, description, is_available)")


class ProductPaginationByCategoryDTO(BaseModel):
    category_id: UUID = Field(
        ..., description="UUID de la categoría para filtrar productos",
    )
    page: int = Field(
        default=1, ge=1, description="Número de página (default: 1)",
    )


# ────────────────────────────── OUTPUT DTOs ────────────────────────────────

class ProductResponseDTO(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    category_id: Optional[UUID] = None
    is_available: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

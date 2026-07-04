import json
from typing import Optional

from fastapi import HTTPException, UploadFile
from pydantic import ValidationError

from src.dto.generation_dtos import CreateGenerationDTO, GenerationType


def validate_create_generation(
    manager_key: str,
    prompt: str,
    req_type: GenerationType,
    model: str,
    referencias_raw: str,
    image: Optional[UploadFile],
) -> CreateGenerationDTO:
    """Parsea y valida los campos del formulario de creación de generación.

    - Convierte `referencias_raw` (JSON string) a `list[UUID]`
    - Valida contra `CreateGenerationDTO`
    - Valida regla de negocio: determinista + imagen → inválido

    Devuelve el DTO validado o lanza HTTPException con el mismo
    formato que `validation_middleware.create_validation_dependency`.
    """
    # ── 1. Parsear referencias ──
    try:
        referencias_list = json.loads(referencias_raw)
        if not isinstance(referencias_list, list):
            raise ValueError("must be a JSON array")
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Errores de validación",
                "code": "VALIDATION_ERROR",
                "details": [
                    {
                        "property": "referencias",
                        "constraints": "Debe ser un array JSON de UUIDs, ej. [\"uuid1\", \"uuid2\"]",
                        "value": referencias_raw,
                    }
                ],
            },
        )

    # ── 2. Validar DTO (Pydantic) ──
    try:
        dto = CreateGenerationDTO(
            manager_key=manager_key,
            prompt=prompt,
            req_type=req_type,
            model=model,
            referencias=referencias_list,
        )
    except ValidationError as e:
        details = [
            {
                "property": ".".join(str(part) for part in err.get("loc", [])),
                "constraints": err.get("msg"),
                "value": err.get("input"),
            }
            for err in e.errors()
        ]
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Errores de validación",
                "code": "VALIDATION_ERROR",
                "details": details,
            },
        )

    # ── 3. Validación cruzada: determinista + imagen prohibido ──
    if dto.req_type == GenerationType.DETERMINISTA and image is not None:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Errores de validación",
                "code": "VALIDATION_ERROR",
                "details": [
                    {
                        "property": "image",
                        "constraints": "No puede enviarse una imagen cuando el tipo de generación es 'determinista'",
                        "value": image.filename,
                    }
                ],
            },
        )

    return dto

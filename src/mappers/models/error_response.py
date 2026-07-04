from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

class ErrorResponse(BaseModel):
    success: bool = False  # Siempre falso para errores
    status: int            # Código HTTP (400, 401, 404, 500, etc.)
    message: str           # Mensaje amigable para el usuario ("Credenciales inválidas")
    error_code: str        # Un código interno para que el frontend lo identifique fácil ("AUTH_FAILED")
    details: Optional[Any] = None # Para capturar errores de validación de formularios, excepciones, etc.
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
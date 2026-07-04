from uuid import UUID

from pydantic import BaseModel

# ────────────────────────────── OUTPUT DTOs ────────────────────────────────

class ManagerKeyResultDTO(BaseModel):
    """Resultado de búsqueda de manager por key.

    Solo retorna los datos necesarios para el flujo de generación.
    """
    id: UUID
    store_id: UUID

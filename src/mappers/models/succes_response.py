from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")
U = TypeVar("U")


class SuccessResponse(BaseModel, Generic[T, U]):
    success: bool = True
    status: int
    message: str
    data: Optional[T] = None
    meta: Optional[U] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
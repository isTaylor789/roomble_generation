from dataclasses import dataclass, field
from typing import Protocol, Optional


@dataclass
class NanoBananaInvoice:
    amount: float
    currency: str = "USD"
    provider: str = ""
    model: str = ""
    tokens: int = 0
    description: Optional[str] = None


@dataclass
class GeneratedImage:
    data: bytes
    mime_type: str


class INanoBanana(Protocol):

    async def generate(
        self,
        *,
        prompt: str,
        images: list[bytes],
        service_tier: Optional[str] = "flex",  # <-- Aquí entra el modo ahorro
        model: str = "google/gemini-3.1-flash-image-preview",
    ) -> tuple[list[GeneratedImage], NanoBananaInvoice]:
        ...

    @staticmethod
    def invoice(raw_response: dict) -> NanoBananaInvoice:
        ...

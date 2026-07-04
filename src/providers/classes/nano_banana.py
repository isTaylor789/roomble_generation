import os
import base64
import struct
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.providers.interfaces.Inano_banana import (
    INanoBanana,
    GeneratedImage,
    NanoBananaInvoice,
)

load_dotenv()

_MODEL_MAX_IMAGES: dict[str, int] = {
    "google/gemini-3.1-flash-image-preview": 6,
    "google/gemini-3-pro-image-preview": 8,
}

_MAGIC_MIME: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),
    (b"BM", "image/bmp"),
]


def _detect_mime(raw: bytes) -> str:
    for magic, mime in _MAGIC_MIME:
        if raw.startswith(magic):
            return mime
    raise ValueError("Cannot detect MIME type from image bytes")


def _to_data_url(raw: bytes) -> str:
    mime = _detect_mime(raw)
    encoded = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


class NanoBanana(INanoBanana):

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or os.getenv("API_KEY")
        self._base_url = base_url or os.getenv("BASE_URL", "https://openrouter.ai/api/v1")

        if not self._api_key:
            raise RuntimeError("API_KEY is required in environment or constructor")

        self._client = AsyncOpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=120.0,  # <-- Agrégale 2 minutotes de paciencia al worker
        )

    # ------------------------------------------------------------------
    # generate
    # ------------------------------------------------------------------

    async def generate(
            self,
            *,
            prompt: str,
            images: list[bytes],
            model: str = "google/gemini-3.1-flash-image-preview",
            service_tier: Optional[str] = "flex",  # <-- Por defecto en flex para el finde
        ) -> tuple[list[GeneratedImage], NanoBananaInvoice]:
            if not images:
                raise ValueError("At least one image is required")
            if not prompt.strip():
                raise ValueError("prompt is required")

            limit = _MODEL_MAX_IMAGES.get(model)
            if limit is None:
                raise ValueError(f"Unknown model: {model}. Supported: {list(_MODEL_MAX_IMAGES.keys())}")
            if len(images) > limit:
                raise ValueError(
                    f"Model {model} supports at most {limit} images per request, got {len(images)}"
                )

            content_parts: list[dict] = [{"type": "text", "text": prompt}]
            for raw in images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": _to_data_url(raw)},
                })
                
            # Armamos los argumentos para la petición
            request_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": content_parts}],
                "extra_body": {"modalities": ["image", "text"]},
            }
            
            # Si service_tier tiene valor, se lo inyectamos (para evitar mandar None y que falle)
            if service_tier:
                request_kwargs["service_tier"] = service_tier

            # <-- LA MAGIA SE APLICA AQUÍ
            response = await self._client.chat.completions.create(**request_kwargs)

            raw_dict = response.model_dump()

            message = response.choices[0].message
            raw_images = getattr(message, "images", None)
            if not raw_images:
                raise RuntimeError("Model returned no images")

            generated: list[GeneratedImage] = []
            for img in raw_images:
                if isinstance(img, dict):
                    url = img["image_url"]["url"]
                else:
                    url = img.image_url.url

                if not url.startswith("data:image/"):
                    raise RuntimeError("Model returned non-data-URL image")

                header, b64 = url.split(",", 1)
                mime = header.split(":")[1].split(";")[0]
                data = base64.b64decode(b64)
                generated.append(GeneratedImage(data=data, mime_type=mime))

            invoice = self.invoice(raw_dict)
            return generated, invoice

    # ------------------------------------------------------------------
    # invoice
    # ------------------------------------------------------------------

    @staticmethod
    def invoice(raw_response: dict) -> NanoBananaInvoice:
        usage: dict = raw_response.get("usage", {})
        cost: float = float(usage.get("cost", 0.0))
        total_tokens: int = int(usage.get("total_tokens", 0))
        provider: str = raw_response.get("provider", "")
        model: str = raw_response.get("model", "")

        prompt_tokens: int = int(usage.get("prompt_tokens", 0))
        completion_tokens: int = int(usage.get("completion_tokens", 0))
        completion_details: dict = usage.get("completion_tokens_details", {})
        image_tokens: int = int(completion_details.get("image_tokens", 0))

        description = (
            f"prompt_tokens={prompt_tokens}, "
            f"completion_tokens={completion_tokens}, "
            f"image_tokens={image_tokens}"
        )

        return NanoBananaInvoice(
            amount=cost,
            currency="USD",
            provider=provider,
            model=model,
            tokens=total_tokens,
            description=description,
        )

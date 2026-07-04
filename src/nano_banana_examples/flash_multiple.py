# google_flash.py
import os
import re
import json
import base64
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("Falta API_KEY en el archivo .env")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

BASE_DIR = Path(__file__).resolve().parent
REF_DIR = BASE_DIR / "references"
OUT_DIR = BASE_DIR / "out"
LOGS_DIR = BASE_DIR / "logs"

OUT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Imagen a modificar
TARGET_IMAGE = REF_DIR / "sala_comedor_6_sillas_y_puerta.jpg"

# Referencias visuales
DINING_REF_IMAGE = REF_DIR / "comedor.jpg"
DOOR_REF_IMAGE = REF_DIR / "puerta_madera.jpg"

for path in [TARGET_IMAGE, DINING_REF_IMAGE, DOOR_REF_IMAGE]:
    if not path.exists():
        raise FileNotFoundError(f"No existe: {path}")


def to_data_url(image_path: Path) -> str:
    ext = image_path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(ext)
    if not mime_type:
        raise ValueError(f"Formato no soportado: {image_path.name}")

    image_bytes = image_path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def sanitize_for_log(obj):
    """
    Limpia data URLs base64 para que el log sea legible.
    Recorre dicts, listas y strings.
    """
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            # Si la clave parece contener una imagen embebida, la limpiamos
            if k in {"url", "image", "image_url"} and isinstance(v, str) and v.startswith("data:image/"):
                cleaned[k] = "[STRIPPED_DATA_IMAGE]"
            else:
                cleaned[k] = sanitize_for_log(v)
        return cleaned

    if isinstance(obj, list):
        return [sanitize_for_log(x) for x in obj]

    if isinstance(obj, str):
        # Reemplaza cualquier data URL de imagen completa por un marcador corto
        return re.sub(
            r"data:image\/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\n\r]+",
            "[STRIPPED_DATA_IMAGE]",
            obj,
        )

    return obj


def save_log(filename_prefix: str, payload: dict):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"{filename_prefix}_{timestamp}.json"

    sanitized = sanitize_for_log(payload)

    with log_path.open("w", encoding="utf-8") as f:
        json.dump(sanitized, f, ensure_ascii=False, indent=2)

    print(f"Log guardado: {log_path}")
    return log_path


prompt = """
You are editing the first image, which is the living room + dining room photo.

Task:
Use the second image as a visual reference for the dining area appearance and the third image as a visual reference for the wooden door appearance.
Edit only the first image.

Important goal:
Keep the living room / sala area intact as much as possible, and only modify the specific target elements so they resemble the provided references.

Rules:
- Edit only the first image.
- Preserve the living room, overall room layout, walls, floor, windows, perspective, geometry, and camera angle.
- Preserve the original lighting and keep the result consistent with the existing illumination.
- Do not redesign the whole room.
- Do not change unrelated objects or areas.
- Use the dining room reference to modify only the dining-related elements in the target image.
- Use the wooden door reference to modify only the door in the target image.
- Keep all modifications photorealistic and naturally integrated.
- Respect scale, shadows, reflections, and perspective.
- Do not add people.
- Do not add extra furniture or decorations beyond what is needed to match the referenced dining set and wooden door style.
- The final result must still look like the same original room, only with those specific elements updated.
"""

request_payload_for_log = {
    "model": "google/gemini-3.1-flash-image-preview",
    "service_tier": "flex",
    "prompt": prompt,
    "input_files": {
        "target_image": str(TARGET_IMAGE),
        "dining_reference": str(DINING_REF_IMAGE),
        "door_reference": str(DOOR_REF_IMAGE),
    },
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": to_data_url(TARGET_IMAGE)},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": to_data_url(DINING_REF_IMAGE)},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": to_data_url(DOOR_REF_IMAGE)},
                },
            ],
        }
    ],
    "extra_body": {
        "modalities": ["image", "text"]
    },
}

save_log("request", request_payload_for_log)

response = client.chat.completions.create(
    model="google/gemini-3.1-flash-image-preview",
    service_tier="flex",
    messages=request_payload_for_log["messages"],
    extra_body=request_payload_for_log["extra_body"],
)

# Guardar respuesta sanitizada
if hasattr(response, "model_dump"):
    response_for_log = response.model_dump()
else:
    # fallback por si la lib devuelve otro tipo de objeto
    response_for_log = json.loads(json.dumps(response, default=str))

save_log("response", response_for_log)

message = response.choices[0].message

if not getattr(message, "images", None):
    raise RuntimeError("El modelo no devolvió imágenes")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

for idx, image in enumerate(message.images, start=1):
    image_url = image["image_url"]["url"] if isinstance(image, dict) else image.image_url.url

    if not image_url.startswith("data:image/"):
        raise RuntimeError("La respuesta no vino como data URL base64")

    header, b64_data = image_url.split(",", 1)

    ext = ".png"
    if "image/jpeg" in header:
        ext = ".jpg"
    elif "image/webp" in header:
        ext = ".webp"

    output_path = OUT_DIR / f"sala_comedor_edit_{timestamp}_{idx}{ext}"
    output_path.write_bytes(base64.b64decode(b64_data))
    print(f"Imagen guardada: {output_path}")
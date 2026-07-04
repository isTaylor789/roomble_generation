# google_flash.py
import os
import base64
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
OUT_DIR.mkdir(parents=True, exist_ok=True)

ROOM_IMAGE = REF_DIR / "sala_de_Estar.jpg"
SOFA_REF_IMAGE = REF_DIR / "sofa_naranja.jpg"

if not ROOM_IMAGE.exists():
    raise FileNotFoundError(f"No existe: {ROOM_IMAGE}")

if not SOFA_REF_IMAGE.exists():
    raise FileNotFoundError(f"No existe: {SOFA_REF_IMAGE}")


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


prompt = """
You are editing the first image, which is the living room photo.

Task:
Place a sofa in the living room using the second image as a visual reference for the sofa's color, style, and general appearance.

Rules:
- Edit only the living room scene in the first image.
- Add a single sofa that matches the orange sofa reference as closely as possible.
- Keep the room layout, walls, floor, windows, lighting, camera angle, and geometry unchanged.
- Do not redesign the room.
- Do not add extra furniture, decorations, people, rugs, lamps, tables, plants, or wall art unless they already exist in the original image.
- The sofa must look naturally placed, correctly scaled, and consistent with the room perspective.
- Respect shadows, occlusions, and the existing lighting conditions.
- Keep the result photorealistic.
"""

response = client.chat.completions.create(
    model="google/gemini-3.1-flash-image-preview",
    service_tier="flex",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": to_data_url(ROOM_IMAGE)},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": to_data_url(SOFA_REF_IMAGE)},
                },
            ],
        }
    ],
    extra_body={
        "modalities": ["image", "text"]
    },
)

message = response.choices[0].message

if not getattr(message, "images", None):
    raise RuntimeError("El modelo no devolvió imágenes")

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

    output_path = OUT_DIR / f"sofa_edit_{idx}{ext}"
    output_path.write_bytes(base64.b64decode(b64_data))
    print(f"Guardado: {output_path}")
import re
from typing import Dict


# Mapeo de extensiones a content types
CONTENT_TYPE_MAP: Dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "ico": "image/x-icon",
}


def get_content_type_from_filename(filename: str) -> str:
    """
    Obtiene el content type MIME basado en la extensión del archivo.
    
    Args:
        filename: Nombre del archivo (ej: "uuid.jpg", "uuid.png")
        
    Returns:
        Content type MIME correspondiente (ej: "image/jpeg")
        
    Raises:
        ValueError: Si no se puede determinar la extensión o no está soportada
    """
    # Regex para extraer la extensión (último punto hasta el final)
    pattern = r'\.([a-zA-Z0-9]+)$'
    match = re.search(pattern, filename)
    
    if not match:
        raise ValueError(f"No se pudo determinar la extensión del archivo '{filename}'")
    
    extension = match.group(1).lower()
    
    content_type = CONTENT_TYPE_MAP.get(extension)
    
    if not content_type:
        raise ValueError(f"Extensión '{extension}' no tiene un content type definido")
    
    return content_type
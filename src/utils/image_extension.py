import re
from typing import List


# Top 10 formatos de imagen más comunes
ALLOWED_EXTENSIONS: List[str] = [
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "webp",
    "svg",
    "tiff",
    "tif",
    "ico",
]


def validate_image_extension(filename: str) -> bool:
    """
    Valida que el archivo tenga una extensión de imagen permitida.
    
    Soporta nombres de archivo complejos como: imagen.cat.jpg, foto.backup.png, etc.
    
    Args:
        filename: Nombre del archivo (ej: "imagen.cat.jpg")
        
    Returns:
        True si la extensión es válida, False en caso contrario
        
    Raises:
        ValueError: Si la extensión no es válida
    """
    # Regex para extraer la extensión (último punto hasta el final)
    pattern = r'\.([a-zA-Z0-9]+)$'
    match = re.search(pattern, filename)
    
    if not match:
        raise ValueError(f"El archivo '{filename}' no tiene una extensión válida")
    
    extension = match.group(1).lower()
    
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(ALLOWED_EXTENSIONS)
        raise ValueError(
            f"Extensión '{extension}' no permitida. "
            f"Extensiones permitidas: {allowed}"
        )
    
    return True

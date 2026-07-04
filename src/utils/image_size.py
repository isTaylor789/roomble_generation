from fastapi import UploadFile


MAX_IMAGE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MiB en bytes


async def validate_image_size(file: UploadFile) -> bool:
    """
    Valida que la imagen no exceda el tamaño máximo permitido (100 MiB).
    
    Args:
        file: Archivo subido por FastAPI
        
    Returns:
        True si el tamaño es válido
        
    Raises:
        ValueError: Si el archivo excede el tamaño máximo
    """
    # Leer el contenido del archivo para obtener su tamaño
    contents = await file.read()
    file_size = len(contents)
    
    # Regresar el cursor al inicio para que pueda leerse de nuevo
    await file.seek(0)
    
    if file_size > MAX_IMAGE_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        max_mb = MAX_IMAGE_SIZE_BYTES / (1024 * 1024)
        raise ValueError(
            f"El archivo es demasiado grande ({size_mb:.2f} MiB). "
            f"Tamaño máximo permitido: {max_mb:.0f} MiB"
        )
    
    return True

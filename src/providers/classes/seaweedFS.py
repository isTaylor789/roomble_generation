import os
import uuid
from botocore.exceptions import ClientError, EndpointConnectionError, ConnectionClosedError

from src.providers.interfaces.IseaweedFS import ISeaweedFS


class SeaweedFS(ISeaweedFS):

    def __init__(self, s3_client, default_bucket: str | None = None):
        self._s3 = s3_client
        self._default_bucket = default_bucket

    def _ensure_bucket_exists(self, bucket: str) -> None:
        """Crea el bucket si no existe"""
        try:
            self._s3.head_bucket(Bucket=bucket)
        except ClientError:
            self._s3.create_bucket(Bucket=bucket)

    # ---------------------------
    # UPLOAD
    # ---------------------------
    def upload_file(
        self,
        *,
        file_bytes: bytes,
        file_name: str,
        content_type: str | None = None,
        bucket: str | None = None,
        prefix: str | None = None
    ) -> str:

        if not file_bytes:
            raise ValueError("file_bytes está vacío")

        if not file_name:
            raise ValueError("file_name es requerido")

        target_bucket = bucket or self._default_bucket
        if not target_bucket:
            raise RuntimeError("Bucket no definido para upload")
        
        # ✅ Extraer solo la extensión del archivo (maneja múltiples puntos)
        _, ext = os.path.splitext(file_name)
        
        # generar nombre único (evita colisiones)
        unique_name = f"{uuid.uuid4()}{ext}"

        if prefix:
            object_key = f"{prefix.rstrip('/')}/{unique_name}"
        else:
            object_key = unique_name

        try:
            self._ensure_bucket_exists(target_bucket)
            self._s3.put_object(
                Bucket=target_bucket,
                Key=object_key,
                Body=file_bytes,
                ContentType=content_type or "application/octet-stream"
            )

        except (EndpointConnectionError, ConnectionClosedError) as e:
            raise RuntimeError(
                f"No se pudo conectar con SeaweedFS ({target_bucket}): {e}"
            ) from e

        except ClientError as e:
            raise RuntimeError(
                f"Error al subir archivo a SeaweedFS: {e}"
            ) from e

        return object_key

    # ---------------------------
    # GET
    # ---------------------------
    def get_file(
        self,
        *,
        file_path: str,
        bucket: str | None = None
    ) -> bytes:

        if not file_path:
            raise ValueError("file_path es requerido")

        target_bucket = bucket or self._default_bucket
        if not target_bucket:
            raise RuntimeError("Bucket no definido para lectura")

        try:
            response = self._s3.get_object(
                Bucket=target_bucket,
                Key=file_path
            )

        except self._s3.exceptions.NoSuchKey:
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        except EndpointConnectionError as e:
            raise RuntimeError("No se pudo conectar con SeaweedFS") from e

        except ClientError as e:
            raise RuntimeError(
                f"Error al obtener archivo desde SeaweedFS: {e}"
            ) from e

        body = response.get("Body")
        if body is None:
            raise RuntimeError("Respuesta inválida desde SeaweedFS")

        return body.read()

    # ---------------------------
    # DELETE
    # ---------------------------
    def delete_file(
        self,
        *,
        file_path: str,
        bucket: str | None = None
    ) -> bool:

        if not file_path:
            raise ValueError("file_path es requerido")

        target_bucket = bucket or self._default_bucket
        if not target_bucket:
            raise RuntimeError("Bucket no definido para delete")

        try:
            # S3 no falla si no existe, pero igual intentamos
            self._s3.delete_object(
                Bucket=target_bucket,
                Key=file_path
            )

        except EndpointConnectionError as e:
            raise RuntimeError("No se pudo conectar con SeaweedFS") from e

        except ClientError as e:
            raise RuntimeError(
                f"Error al eliminar archivo en SeaweedFS: {e}"
            ) from e

        return True

    # ---------------------------
    # UPDATE
    # ---------------------------
    def update_file(
        self,
        *,
        file_path: str,
        new_file_bytes: bytes,
        content_type: str | None = None,
        bucket: str | None = None
    ) -> bool:

        if not file_path:
            raise ValueError("file_path es requerido")

        if not new_file_bytes:
            raise ValueError("new_file_bytes está vacío")

        target_bucket = bucket or self._default_bucket
        if not target_bucket:
            raise RuntimeError("Bucket no definido para update")

        try:
            # 1️⃣ eliminar archivo anterior
            self._s3.delete_object(
                Bucket=target_bucket,
                Key=file_path
            )

            # 2️⃣ subir el nuevo contenido con el MISMO key
            self._s3.put_object(
                Bucket=target_bucket,
                Key=file_path,
                Body=new_file_bytes,
                ContentType=content_type or "application/octet-stream"
            )

        except EndpointConnectionError as e:
            raise RuntimeError("No se pudo conectar con SeaweedFS") from e

        except ClientError as e:
            raise RuntimeError(
                f"Error al actualizar archivo en SeaweedFS: {e}"
            ) from e

        return True
    
    def exists_file(
        self,
        *,
        file_path: str,
        bucket: str | None = None
    ) -> bool:

        if not file_path:
            return False

        target_bucket = bucket or self._default_bucket
        
        if not target_bucket:
            raise RuntimeError("Bucket no definido para exists")

        response = self._s3.head_object(
            Bucket=target_bucket,
            Key=file_path
        )

        # pattern result puro:
        # si head_object no lanza excepción → existe
        return response is not None

        
        
        
        
        
        
        
        
        
        
        
from abc import ABC, abstractmethod


class ISeaweedFS(ABC):
    @abstractmethod
    def upload_file(
        self,
        *,
        file_bytes: bytes,
        file_name: str,
        content_type: str | None = None,
        bucket: str | None = None,
        prefix: str | None = None
    ) -> str:
        """
        Sube un archivo al storage.

        Retorna:
            str -> filepath o filename generado
        """
        raise NotImplementedError

    @abstractmethod
    def get_file(
        self,
        *,
        file_path: str,
        bucket: str | None = None
    ) -> bytes:
        """
        Obtiene un archivo desde storage.

        Retorna:
            bytes -> contenido del archivo
        """
        raise NotImplementedError

    @abstractmethod
    def delete_file(
        self,
        *,
        file_path: str,
        bucket: str | None = None
    ) -> bool:
        """
        Elimina un archivo del storage.

        Retorna:
            bool -> True si se eliminó correctamente
        """
        raise NotImplementedError

    @abstractmethod
    def update_file(
        self,
        *,
        file_path: str,
        new_file_bytes: bytes,
        content_type: str | None = None,
        bucket: str | None = None
    ) -> bool:
        """
        Reemplaza un archivo existente manteniendo el mismo path.

        Retorna:
            bool -> True si la operación fue exitosa
        """
        raise NotImplementedError
    
    @abstractmethod
    def exists_file(
        self,
        *,
        file_path: str,
        bucket: str | None = None
    ) -> bool:
        """
        Verifica si un archivo existe en el storage.

        Retorna:
            bool -> True si existe, False si no
        """
        raise NotImplementedError
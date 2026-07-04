import logging
from src.providers.interfaces.IseaweedFS import ISeaweedFS
from src.providers.interfaces.Iredis_cache import IRedisCache

logger = logging.getLogger(__name__)

_IMAGE_CACHE_TTL = 20 * 60  # 20 minutos
_IMAGE_CACHE_PREFIX = "img_cache"


class ImageLoader:
    """Descarga imágenes de SeaweedFS con caché en Redis para evitar
    descargas repetidas de productos de referencia (catálogo).

    Cache key: ``img_cache:{bucket}:{file_path}``
    TTL: 20 min — suficiente para ráfagas de generaciones del mismo store.
    """

    def __init__(self, seaweed_fs: ISeaweedFS, redis_cache: IRedisCache) -> None:
        self._seaweed = seaweed_fs
        self._redis = redis_cache

    def _cache_key(self, bucket: str, file_path: str) -> str:
        return f"{_IMAGE_CACHE_PREFIX}:{bucket}:{file_path}"

    async def load(self, *, bucket: str, file_path: str) -> bytes:
        if not file_path:
            raise ValueError("file_path is required")
        if not bucket:
            raise ValueError("bucket is required")

        cache_key = self._cache_key(bucket, file_path)

        cached = await self._redis.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit — bucket=%s path=%s", bucket, file_path)
            return cached

        logger.debug("Cache miss — downloading bucket=%s path=%s", bucket, file_path)
        data = self._seaweed.get_file(file_path=file_path, bucket=bucket)

        await self._redis.set(key=cache_key, value=data, ttl=_IMAGE_CACHE_TTL)
        logger.debug("Cached — bucket=%s path=%s size=%d", bucket, file_path, len(data))

        return data

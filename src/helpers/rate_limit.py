import json
import time
from typing import Any

from fastapi import HTTPException
from redis.asyncio import Redis


# ── Constantes del bucket ──
MAX_TOKENS = 1200
REFILL_WINDOW_SECONDS = 16 * 60 * 60  # 16 horas
TOKENS_PER_SECOND = MAX_TOKENS / REFILL_WINDOW_SECONDS  # ≈ 0.020833

# ── Costo por modelo (fichas que consume cada request) ──
MODEL_COST: dict[str, int] = {
    "google/gemini-3.1-flash-image-preview": 8,
    "google/gemini-3-pro-image-preview": 32,
}

# ── Prefijos de keys en Redis ──
_KEY_MANAGER = "manager:"
_KEY_RATE = "rate_limit:"

# ── TTLs ──
_CACHE_MANAGER_TTL = 9 * 60 * 60         # 9 horas
_RATE_BUCKET_TTL = REFILL_WINDOW_SECONDS  # 16 horas

# ─────────────────────────────────────────────
# Lua script atómico para el token bucket
# ─────────────────────────────────────────────
# Usa una Redis HASH con campos:
#   t → tokens restantes (float)
#   r → timestamp del último refill (float)
#
# KEYS[1] = rate_limit:{manager_key}
# ARGV[1] = costo en fichas
# ARGV[2] = now (epoch)
# ARGV[3] = max_tokens
# ARGV[4] = tokens_per_second
# ARGV[5] = bucket_ttl (segundos)
#
# Retorna {1, remaining}        → éxito
#         {0, available, wait_s} → sin fichas
_LUA_CONSUME = """
local key = KEYS[1]
local cost = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local max_tokens = tonumber(ARGV[3])
local tokens_per_sec = tonumber(ARGV[4])
local bucket_ttl = tonumber(ARGV[5])

local t_raw = redis.call("HGET", key, "t")
local r_raw = redis.call("HGET", key, "r")

local tokens, last_refill

if t_raw == false or r_raw == false then
    tokens = max_tokens - cost
    last_refill = now
    redis.call("HMSET", key, "t", tokens, "r", last_refill)
    redis.call("EXPIRE", key, bucket_ttl)
    return {1, math.floor(tokens)}
end

tokens = tonumber(t_raw)
last_refill = tonumber(r_raw)

local elapsed = now - last_refill
local refill = elapsed * tokens_per_sec
tokens = math.min(max_tokens, tokens + refill)

if tokens < cost then
    local wait_s = math.ceil((cost - tokens) / tokens_per_sec)
    return {0, math.floor(tokens), wait_s}
end

tokens = tokens - cost
redis.call("HMSET", key, "t", tokens, "r", now)
redis.call("EXPIRE", key, bucket_ttl)

return {1, math.floor(tokens)}
"""


class RateLimiter:
    """Rate limiter token bucket con Redis (operaciones atómicas via Lua).

    Cada manager tiene un bucket de {MAX_TOKENS} fichas que se
    regeneran a razón de {TOKENS_PER_SECOND:.4f} ficha/s
    (refill completo cada {REFILL_WINDOW_SECONDS / 3600:.0f}h).
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    # ────────────────────────────────
    # 1. Cache de manager_key
    # ────────────────────────────────

    async def manager_key_exists(self, manager_key: str) -> bool:
        """Verifica si un manager_key está cacheado en Redis.

        Returns:
            ``True`` si la key existe, ``False`` si no (sin error).
        """
        key = f"{_KEY_MANAGER}{manager_key}"
        exists = await self._redis.exists(key)
        return bool(exists)

    async def get_cached_manager(self, manager_key: str) -> dict[str, Any] | None:
        """Obtiene los datos del manager previamente cacheados.

        Returns:
            ``dict`` con los datos, o ``None`` si no está cacheado.
        """
        key = f"{_KEY_MANAGER}{manager_key}"
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def cache_manager_key(self, manager_key: str, data: dict[str, Any]) -> None:
        """Cachea los datos del manager en Redis por 9 horas.

        Args:
            manager_key: Key única del manager.
            data: Dict con la info del manager (manager_id, store_id, etc.).
        """
        key = f"{_KEY_MANAGER}{manager_key}"
        encoded = json.dumps(data, default=str)
        await self._redis.set(key, encoded, ex=_CACHE_MANAGER_TTL)

    # ────────────────────────────────
    # 2. Costo por modelo
    # ────────────────────────────────

    @staticmethod
    def get_model_cost(model: str) -> int:
        """Retorna el costo en fichas del modelo.

        Raises:
            HTTPException[400]: Si el modelo no está en ``MODEL_COST``.
        """
        cost = MODEL_COST.get(model)
        if cost is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Modelo no soportado",
                    "code": "INVALID_MODEL",
                    "details": [
                        {
                            "property": "model",
                            "constraints": (
                                f"El modelo '{model}' no está habilitado. "
                                f"Válidos: {', '.join(MODEL_COST)}"
                            ),
                            "value": model,
                        }
                    ],
                },
            )
        return cost

    # ────────────────────────────────
    # 3. Authorize + charge (combinado)
    # ────────────────────────────────

    async def authorize_and_charge(
        self,
        manager_key: str,
        model: str,
        manager_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Cachea datos del manager (si se proveen) y cobra fichas del bucket.

        - Si ``manager_data`` no es ``None``, lo cachea en Redis primero.
        - Luego cobra las fichas del modelo.
        - Retorna los datos del manager cacheados.

        Los errores (modelo inválido, fichas insuficientes) se manejan
        via ``HTTPException`` que el middleware ``error_handler_middleware``
        formatea automáticamente.
        """
        if manager_data is not None:
            await self.cache_manager_key(manager_key, manager_data)

        await self.check_rate_limit(manager_key, model)

        cached = await self.get_cached_manager(manager_key)
        if cached is None:
            raise HTTPException(
                status_code=500,
                detail="No se pudieron recuperar los datos del manager tras la autorización",
            )

        return cached

    # ────────────────────────────────
    # 4. Token bucket — rate limit
    # ────────────────────────────────

    async def check_rate_limit(self, manager_key: str, model: str) -> int:
        """Verifica y consume fichas del bucket del manager (atómico via Lua).

        Args:
            manager_key: Key del manager.
            model: Identificador del modelo.

        Returns:
            ``int`` — fichas restantes después de consumir.

        Raises:
            HTTPException[400]: Si el modelo no está en ``MODEL_COST``.
            HTTPException[429]: Si no hay fichas suficientes.
        """
        cost = self.get_model_cost(model)

        if cost > MAX_TOKENS:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Configuración inválida",
                    "code": "INTERNAL_ERROR",
                    "details": [
                        {
                            "property": "model",
                            "constraints": (
                                f"El costo del modelo ({cost}) excede "
                                f"el máximo del bucket ({MAX_TOKENS})"
                            ),
                            "value": model,
                        }
                    ],
                },
            )

        key = f"{_KEY_RATE}{manager_key}"
        now = time.time()

        result = await self._redis.eval(
            _LUA_CONSUME,
            1,  # numkeys
            key,
            cost,
            now,
            MAX_TOKENS,
            TOKENS_PER_SECOND,
            _RATE_BUCKET_TTL,
        )

        # result[0] == 1 → éxito, result[0] == 0 → sin fichas
        if result[0] == 0:
            available = int(result[1])
            wait_seconds = int(result[2])
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Sin peticiones disponibles",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "details": [
                        {
                            "property": "rate_limit",
                            "constraints": (
                                f"Fichas disponibles: {available}, "
                                f"requeridas: {cost}. "
                                f"Reintenta en {wait_seconds}s."
                            ),
                            "value": {
                                "available": available,
                                "required": cost,
                                "retry_after_seconds": wait_seconds,
                            },
                        }
                    ],
                },
            )

        return int(result[1])

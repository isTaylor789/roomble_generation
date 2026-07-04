from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ── Mapa: tipo de excepción → (status_code, error_code, mensaje genérico) ──
_EXCEPTION_MAP: list[tuple[type[Exception], int, str, str]] = [
    (ValueError,          404, "NOT_FOUND",           "Resource not found"),
    (PermissionError,     403, "FORBIDDEN",           "Forbidden"),
    (NotImplementedError, 501, "NOT_IMPLEMENTED",     "Not implemented"),
    (TimeoutError,        504, "GATEWAY_TIMEOUT",     "Request timed out"),
    (ConnectionError,     503, "SERVICE_UNAVAILABLE", "External service unavailable"),
    (SQLAlchemyError,     500, "DATABASE_ERROR",      "Database error"),
    (RuntimeError,        500, "INTERNAL_ERROR",      "Internal server error"),
]


def _build_error_body(
    status: int,
    error_code: str,
    message: str,
    details = None,
) -> dict:
    return {
        "success": False,
        "status": status,
        "error_code": error_code,
        "message": message,
        "details": details,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTPException lanzadas explícitamente con raise HTTPException(...)."""
    status_code = exc.status_code

    # Mapear status a error_code genérico
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
    }
    error_code = code_map.get(status_code, "HTTP_ERROR")
    detail = exc.detail

    # Si detail es un dict (como el que arma validation_middleware), lo pasamos como details
    details = None
    message = "HTTP error"
    if isinstance(detail, dict):
        details = detail.get("details")
        message = detail.get("message", detail.get("code", "HTTP error"))
    elif isinstance(detail, str):
        message = detail

    logger.warning("HTTPException [%s] %s — %s", status_code, request.url, message)

    return JSONResponse(
        status_code=status_code,
        content=_build_error_body(status_code, error_code, message, details),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    """Errores de validación de Pydantic (body/query/route mal formados)."""
    errors = [
        {
            "field": " → ".join(str(loc) for loc in err["loc"]),
            "reason": err["msg"],
        }
        for err in exc.errors()
    ]

    logger.warning("ValidationError %s — %s", request.url, errors)

    return JSONResponse(
        status_code=422,
        content=_build_error_body(
            status=422,
            error_code="VALIDATION_ERROR",
            message="Validation failed",
            details=errors,
        ),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Captura cualquier excepción no controlada.
    Recorre _EXCEPTION_MAP; si no hay match → 500 INTERNAL_ERROR.
    """
    for exc_type, status_code, error_code, default_message in _EXCEPTION_MAP:
        if isinstance(exc, exc_type):
            # Para 4xx exponemos el mensaje real como details; para 5xx no.
            details = str(exc) if status_code < 500 else None

            if status_code >= 500:
                logger.exception("Unhandled %s at %s", type(exc).__name__, request.url)
            else:
                logger.warning(
                    "%s [%s] %s — %s", type(exc).__name__, status_code, request.url, exc,
                )

            return JSONResponse(
                status_code=status_code,
                content=_build_error_body(status_code, error_code, default_message, details),
            )

    # Fallback total
    logger.exception("Unknown exception at %s", request.url)
    return JSONResponse(
        status_code=500,
        content=_build_error_body(500, "INTERNAL_ERROR", "Unexpected internal server error"),
    )

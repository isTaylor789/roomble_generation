from typing import Any, Optional, TypeVar

from src.mappers.models.succes_response import SuccessResponse
from src.mappers.models.error_response import ErrorResponse

T = TypeVar("T")
U = TypeVar("U")


def _to_response(
    status: int,
    message: str,
    data: Optional[T] = None,
    meta: Optional[U] = None,
) -> SuccessResponse[Optional[T], Optional[U]]:
    return SuccessResponse(
        status=status,
        message=message,
        data=data,
        meta=meta,
    )


def to_success_response(
    data: T,
    message: str = "Operation successful",
) -> SuccessResponse[T, Optional[Any]]:
    return _to_response(status=200, message=message, data=data)


def to_created_response(
    data: T,
    message: str = "Resource created successfully",
) -> SuccessResponse[T, Optional[Any]]:
    return _to_response(status=201, message=message, data=data)


def to_accepted_response(
    data: Optional[T] = None,
    message: str = "Request accepted for processing",
) -> SuccessResponse[Optional[T], Optional[Any]]:
    return _to_response(status=202, message=message, data=data)


def to_no_content_response(
    message: str = "Operation completed successfully",
) -> SuccessResponse[Optional[Any], Optional[Any]]:
    return _to_response(status=204, message=message)


def to_response_with_meta(
    data: T,
    meta: U,
    message: str = "Operation successful",
    status: int = 200,
) -> SuccessResponse[T, U]:
    return _to_response(status=status, message=message, data=data, meta=meta)

# ____________________________________
# Errir response 
# ____________________________________

def to_bad_request_response(
    message: str = "Bad Request", 
    error_code: str = "BAD_REQUEST", 
    details: Optional[Any] = None
) -> ErrorResponse:
    return ErrorResponse(status=400, message=message, error_code=error_code, details=details)

def to_not_found_response(
    message: str = "Resource not found", 
    error_code: str = "NOT_FOUND"
) -> ErrorResponse:
    return ErrorResponse(status=404, message=message, error_code=error_code)

def to_internal_error_response(
    message: str = "An unexpected error occurred", 
    error_code: str = "INTERNAL_SERVER_ERROR"
) -> ErrorResponse:
    return ErrorResponse(status=500, message=message, error_code=error_code)


from typing import Callable, Literal, Type, TypeVar, Any

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)
SourceType = Literal["body", "query", "route"]


def create_validation_dependency(
    model: Type[T],
    source: SourceType = "body",
) -> Callable[[Request], T]:
    """
    Crea una dependencia que valida body/query/route contra un Pydantic model.
    Uso en un controlador:

        @router.post("/users")
        async def create_user(
            dto: UserCreateDTO = Depends(create_validation_dependency(UserCreateDTO, "body"))
        ):
            ...
    """

    async def dependency(request: Request) -> T:
        # Obtener datos según la fuente
        if source == "body":
            try:
                raw: Any = await request.json()
            except Exception:
                raw = {}
        elif source == "query":
            raw = dict(request.query_params)
        elif source == "route":
            raw = dict(request.path_params)
        else:
            raise RuntimeError("Invalid source for validation")

        # Intentar mapear al DTO (Pydantic)
        try:
            dto = model(**raw)
        except ValidationError as e:
            details = [
                {
                    "property": ".".join(str(part) for part in err.get("loc", [])),
                    "constraints": err.get("msg"),
                    "value": err.get("input"),
                }
                for err in e.errors()
            ]

            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Errores de validación",
                    "code": "VALIDATION_ERROR",
                    "details": details,
                },
            )

        # Guardar el DTO validado en request.state (similar a HttpContext.Items)
        setattr(request.state, f"validated_{source}", dto)

        return dto

    return dependency
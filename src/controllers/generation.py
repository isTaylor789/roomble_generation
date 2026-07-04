import json
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse

from src.conf.container import container
from src.dto.generation_dtos import GenerationType
from src.mappers.response_mappers import to_created_response
from src.utils.generation_validator import validate_create_generation

router = APIRouter(
    prefix="/api/v1/generations",
    tags=["Generations"],
)


@router.post(
    "/job",
    status_code=status.HTTP_201_CREATED,
    summary="Create a generation job id",
)
async def create_generation(
    manager_key: str = Form(...),
    prompt: str = Form(...),
    req_type: GenerationType = Form(...),
    model: str = Form(...),
    referencias: str = Form(...),
    image: Optional[UploadFile] = File(None),
):
    dto = validate_create_generation(
        manager_key=manager_key,
        prompt=prompt,
        req_type=req_type,
        model=model,
        referencias_raw=referencias,
        image=image,
    )

    result = await container.generation_service.create(dto=dto, image=image)

    return to_created_response(
        data=result,
        message="Generation created successfully",
    )


@router.get(
    "/{idem_key}/stream",
    summary="SSE stream — sigue el progreso de una generación en tiempo real",
)
async def stream_generation(idem_key: str):
    """FSM: processing → completed | failed.

    Eventos SSE (``event: status``):
      - ``{"step":"processing","idem_key":"...","generation_id":"..."}``
      - ``{"step":"completed","idem_key":"...","generation_id":"...","output_path":"..."}``
      - ``{"step":"failed","idem_key":"...","generation_id":"...","error":"..."}``

    La conexión se cierra automáticamente al recibir ``completed`` o ``failed``.
    Soporta late-join: si la generación ya terminó, retorna el evento final inmediatamente.
    """
    async def event_generator():
        redis = container.redis_cache

        # 1. Late-join: Ver el estado actual en caché
        cached = await redis.get(f"gen_status:{idem_key}")
        if cached is not None:
            event = json.loads(cached)
            yield f"event: status\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"
            
            # Solo cerramos la conexión si el proceso YA es terminal.
            # Si es "processing", ignoramos el if y seguimos al PubSub.
            if event.get("step") in ("completed", "failed"):
                return

        # 2. Suscribirse a PubSub
        channel = f"generation:{idem_key}"
        async for event in redis.subscribe(channel):
            yield f"event: status\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"
            if event.get("step") in ("completed", "failed"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
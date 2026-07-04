# Endpoints — Generation

## POST /api/v1/generations/job

Crea una solicitud de generación. Valida al manager, cobra fichas del rate limit, sube la imagen (si aplica) y encola el trabajo en Redis.

### Request

```curl
curl -X POST http://localhost:8000/api/v1/generations/job \
  -H "accept: application/json" \
  -F "manager_key=KEY_DEL_MANAGER" \
  -F "prompt=Genera una imagen de un producto con estilo minimalista" \
  -F "req_type=abierto" \
  -F "model=google/gemini-3.1-flash-image-preview" \
  -F 'referencias=["550e8400-e29b-41d4-a716-446655440000","660e8400-e29b-41d4-a716-446655440001"]' \
  -F "image=@/ruta/a/imagen.jpg"
```

### Campos del form-data

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `manager_key` | string | sí | Clave única del manager (max 30 chars) |
| `prompt` | string | sí | Prompt descriptivo para la generación |
| `req_type` | string | sí | `determinista` o `abierto` |
| `model` | string | sí | ID del modelo de IA (ej. `google/gemini-3.1-flash-image-preview`) |
| `referencias` | string | sí | JSON array de UUIDs de productos de referencia |
| `image` | file | no | Archivo de imagen (solo si `req_type=abierto`) |

### Notas

- Si `req_type=determinista` y se envía `image`, la API responde 400.
- `referencias` se envía como string JSON, no como campo repetido.
- La imagen se valida: extensión permitida y tamaño máximo 100 MiB.
- Si `req_type=abierto` sin imagen, el campo `input_image_path` no se incluye en el payload encolado.
- La respuesta incluye un `idem_key` (UUID v4) que sirve como identificador único de la solicitud para tracking y desduplicación.

### Ejemplo sin imagen (determinista)

```curl
curl -X POST http://localhost:8000/api/v1/generations/job \
  -H "accept: application/json" \
  -F "manager_key=KEY_DEL_MANAGER" \
  -F "prompt=Genera una descripción de producto" \
  -F "req_type=determinista" \
  -F "model=google/gemini-3.1-flash-image-preview" \
  -F 'referencias=["550e8400-e29b-41d4-a716-446655440000"]'
```
otro ejemplo:
```curl
curl -X POST http://localhost:8000/api/v1/generations/job   
-H "accept: application/json"   
-F "manager_key=sk-1a2b3c4d5e6f"   
-F "prompt=Diseña una habitación de estar moderna y acogedora basada en la imagen proporcionada. Integra un sofá de dos plazas en azul cobalto, un comedor clásico de lujo en una zona definida, y un armario de madera de roble contra la pared. El suelo debe mantener un estilo de loseta de cruces geométricas. El ambiente debe ser elegante, equilibrado y funcional."   
-F "req_type=abierto"   
-F "model=google/gemini-3.1-flash-image-preview"   
-F 'referencias=["04d0b8ff-6a40-4f4c-bc53-4bd3a033d466","108a4284-b1cd-4101-bdf3-cfec1c1d1a31","16d11f5f-80be-41a1-b1ed-0eed0569b0fe","17442a1c-ba12-4164-bd92-0b695d19f856"]'   
-F "image=@/home/maverick/Documentos/testing/references/cuarto_vacio.jpg"
```
response
```json
{"success":true,"status":201,"message":"Generation created successfully","data":{"idem_key":"32d0b3d8-323c-4a29-953c-82b6c2f81914","state":"process"},"meta":null,"timestamp":"2026-06-21T05:50:58.126890"}
```

---

## GET /api/v1/generations/{idem_key}/stream

SSE (Server-Sent Events) — notifica el progreso de una generación en tiempo real.

### FSM de estados

```
processing ──→ completed
     └──────→ failed
```

### Request

```curl
curl -N http://localhost:8000/api/v1/generations/<idem_key>/stream
```

### Eventos SSE

Todos los eventos usan `event: status`.

**processing** — el worker tomó el job y está procesando:
```
event: status
data: {"step":"processing","idem_key":"...","generation_id":"..."}
```

**completed** — generación exitosa:
```
event: status
data: {"step":"completed","idem_key":"...","generation_id":"...","output_path":"generation/output/..."}
```

**failed** — error durante la generación:
```
event: status
data: {"step":"failed","idem_key":"...","generation_id":"...","error":"..."}
```

real:
```bash
curl -N http://localhost:8000/api/v1/generations/32d0b3d8-323c-4a29-953c-82b6c2f81914/stream
event: status
data: {"step":"processing","idem_key":"32d0b3d8-323c-4a29-953c-82b6c2f81914","generation_id":"59887770-6911-4216-89d6-3ad1aeb42ab4"}

event: status
data: {"step":"completed","idem_key":"32d0b3d8-323c-4a29-953c-82b6c2f81914","generation_id":"59887770-6911-4216-89d6-3ad1aeb42ab4","output_path":"75fdc440-ae1e-40c5-8e32-af55843f5c16.png"}
```

### Notas

- La conexión se cierra automáticamente al recibir `completed` o `failed`.
- Late-join: si el cliente se conecta después de que la generación terminó, recibe el evento final inmediatamente (cache Redis con TTL 1h).
- El campo `output_path` no es la URL de descarga, es la ruta interna en SeaweedFS (bucket `generation`).
- No se expone la imagen generada por este endpoint — otro microservicio se encarga de servirla.

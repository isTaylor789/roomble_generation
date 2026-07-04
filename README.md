# Roomble Generation

Microservicio de generación de imágenes con IA. Orquesta el pipeline completo: recibe solicitudes con imágenes de referencia, llama a modelos Gemini vía OpenRouter, persiste resultados en SeaweedFS y notifica en tiempo real vía SSE.

## Stack

| Capa | Tecnología |
|---|---|
| API | FastAPI (async) |
| IA | OpenRouter → `google/gemini-3.1-flash-image-preview` / `google/gemini-3-pro-image-preview` |
| Storage | SeaweedFS (S3-compatible) |
| Colas / PubSub / Cache | Redis (FIFO queues + PubSub + image cache) |
| DB | PostgreSQL + SQLAlchemy async |
| Rate Limit | Token bucket atómico Redis + Lua scripting |

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/generations/job` | Crea un job de generación → retorna `idem_key` |
| `GET` | `/api/v1/generations/{idem_key}/stream` | SSE — sigue el progreso en tiempo real |

Ver [docs/generation_endpoints.md](docs/generation_endpoints.md) para detalles de request/response.

## Flujo completo

```
POST /job
  │
  ├─ Controller → valida DTO + imagen
  ├─ Service   → autoriza manager (rate limit), sube imagen a SeaweedFS, encola en Redis
  └─ Response  → {idem_key, state: "process"}
  
Scheduler (poll 5s)
  └─ Worker (semáforo=1, FIFO 1 a la vez)
       ├─ 1. INSERT generation (PENDING)
       ├─ 2. INSERT generation_products (referencias)
       ├─ 3. UPDATE status=PROCESSING  →  PUBLISH sse
       ├─ 4. ImageLoader: descarga imgs con cache Redis 20min
       ├─ 5. NanoBanana.generate() → OpenRouter Gemini
       ├─ 6. SeaweedFS.upload_file() → bucket generation
       ├─ 7. UPDATE status=COMPLETED  →  PUBLISH sse
       └─ 8. INSERT cost_ledger (invoice)
       
       Error → UPDATE status=FAILED  →  PUBLISH sse
  
GET /{idem_key}/stream
  └─ SSE ← Redis PubSub channel generation:{idem_key}
       events: processing → completed | failed
       late-join: Redis cache TTL 1h
```

## Estructura

```
src/
├── conf/              # DI Container, DB, Routes
├── controllers/       # Endpoints HTTP
├── dto/               # Pydantic models
├── entities/          # SQLAlchemy models + enums
├── helpers/           # RateLimiter (Redis+Lua), pagination
├── mappers/           # Response builders (SuccessResponse, ErrorResponse)
├── middlewares/       # Error handler, validation
├── providers/         # RedisCache, SeaweedFS, NanoBanana
├── repositories/      # SQL operations (interfaces + implementations)
├── services/          # Business logic orchestration
├── utils/             # Image validation, generation validator
└── worker/            # Scheduler, Worker, handlers
```

## Proveedores

### NanoBanana (`providers/classes/nano_banana.py`)
Wrapper sobre OpenRouter para modelos Gemini de generación de imágenes.

- `generate(prompt, images, model)` → `(list[GeneratedImage], NanoBananaInvoice)`
- `invoice(raw_response)` → `NanoBananaInvoice` (amount, tokens, provider, model, description)

Límites por modelo: flash ≤6 imágenes, pro ≤8 imágenes.

### RedisCache (`providers/classes/redis_cache.py`)
- Cache de imágenes (TTL 20min)
- Colas FIFO por manager (`queue:manager:{id}`)
- PubSub para notificaciones SSE (`generation:{idem_key}`)
- Persistencia de último estado (`gen_status:{idem_key}`, TTL 1h)

### SeaweedFS (`providers/classes/seaweedFS.py`)
Storage S3-compatible. Buckets usados:

| Bucket | Contenido |
|---|---|
| `input_images` | Imágenes subidas por el usuario (`req_type=abierto`) |
| `products` | Imágenes de catálogo de productos de referencia |
| `generation` | Imágenes generadas por la IA (output) |

## Worker Pipeline

### ImageLoader (`worker/handler/image_loader.py`)
Descarga imágenes de SeaweedFS con caché Redis de 20min. Ideal para productos de catálogo que se reutilizan entre generaciones del mismo store.

### Scheduler (`worker/scheduler.py`)
Escanea colas FIFO en Redis (`queue:manager:*`) cada 5s, hace pop atómico y dispatchea al Worker. El worker tiene semáforo=1 → procesamiento secuencial.

### Worker (`worker/worker.py`)
Pipeline completo de 8 pasos. Notifica cada transición de la FSM vía Redis PubSub. Los estados son: `PENDING → PROCESSING → COMPLETED | FAILED`.

## Rate Limiting

Token bucket atómico con Redis + Lua:
- 1200 fichas por manager, refill en 16h
- `gemini-3.1-flash-image-preview`: 8 fichas/request
- `gemini-3-pro-image-preview`: 32 fichas/request

## Variables de entorno

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string async |
| `API_KEY` | OpenRouter API key |
| `BASE_URL` | OpenRouter base URL (default: `https://openrouter.ai/api/v1`) |
| `SEAWEED_S3_ENDPOINT` | SeaweedFS S3 endpoint |
| `SEAWEED_S3_ACCESS_KEY` | S3 access key |
| `SEAWEED_S3_SECRET_KEY` | S3 secret key |
| `SEAWEED_S3_BUCKET` | Default bucket (default: `datasources`) |
| `REDIS_HOST` | Redis host |
| `REDIS_PORT` | Redis port |
| `REDIS_PASSWORD` | Redis password (opcional) |

## Documentación

- [Endpoints de generación](docs/generation_endpoints.md)
- [Arquitectura](docs/architecture.md)

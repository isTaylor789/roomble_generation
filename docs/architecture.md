# Arquitectura — Roomble Manager

```
src/
├── conf/                         # Configuración y wiring (DI Container + DB + Routes)
│   ├── container.py              # Composition Root — instancia repos, services, providers, helpers
│   ├── db.py                     # Engine async + session factory + Base declarativa
│   └── routes.py                 # Registro de routers de controllers
│
├── controllers/                  # Capa más externa — recibe request, delega al service
│   ├── generation.py             # POST /api/v1/generations/job — crear generación
│   └── product.py                # CRUD de productos (referencial)
│
├── dto/                          # Validación de entrada/salida entre capas (Pydantic)
│   ├── generation_dtos.py        # CreateGenerationDTO, GenerationResponseDTO, GenerationType
│   ├── generation_product.py     # (reservado)
│   ├── manager_dtos.py           # ManagerIdDTO, ManagerKeyResultDTO, ManagerResponseDTO
│   └── product_dtos.py           # CreateProductDTO, ProductResponseDTO (referencial)
│
├── entities/                     # Modelos SQLAlchemy → tablas en BD
│   ├── enums/
│   │   ├── generation_status.py  # GenerationStatus: PENDING, PROCESSING, COMPLETED, FAILED
│   │   └── __init__.py
│   ├── generation.py             # generations — solicitud de generación
│   ├── generation_product.py     # generation_products — relación N:N generations ↔ products
│   ├── cost_ledger.py            # cost_ledger — registro de costos por generación
│   ├── manager.py                # managers — gerentes que solicitan generaciones
│   ├── product.py                # products — productos de referencia (referencial)
│   ├── category.py               # (referencial)
│   └── store.py                  # (referencial)
│
├── helpers/                      # Utilidades globales y reutilizables
│   ├── pagination_template.py    # build_pagination_meta — metadata de paginación
│   └── rate_limit.py             # RateLimiter — token bucket atómico con Redis + Lua
│
├── mappers/                      # Estandarización de respuestas HTTP
│   ├── models/
│   │   ├── error_response.py     # ErrorResponse — formato único de error
│   │   └── succes_response.py    # SuccessResponse — formato único de éxito
│   └── response_mappers.py       # to_created_response, to_success_response, etc.
│
├── middlewares/                  # Interceptores de request/response
│   ├── error_handler_middleware.py  # Captura HTTPException y no controladas → ErrorResponse
│   └── validation_middleware.py     # create_validation_dependency — valida body/query/route
│
├── providers/                    # Abstracción de servicios externos
│   ├── classes/
│   │   ├── nano_banana.py        # NanoBanana — wrapper OpenRouter Gemini (generate + invoice)
│   │   ├── redis_cache.py        # RedisCache — get/set + colas FIFO + pubsub + cache imgs
│   │   └── seaweedFS.py         # SeaweedFS — S3-compatible storage
│   └── interfaces/
│       ├── Inano_banana.py       # INanoBanana — Protocol (generate, invoice)
│       ├── Iredis_cache.py       # IRedisCache — Protocol (set/get/queue/pubsub)
│       └── IseaweedFS.py        # ISeaweedFS — Protocol (upload/get/delete)
│
├── repositories/                 # Operaciones de base de datos (SQL)
│   ├── classes/
│   │   ├── generation_repository.py         # create(manager_id, store_id, ...) → bool
│   │   ├── generation_product_repository.py # create(generation_id, product_id) → bool
│   │   ├── cost_ledger_repository.py        # create(manager_id, store_id, amount, ...) → bool
│   │   ├── manager_repository.py            # find_by_id, find_by_key, list_paginated
│   │   └── product_repository.py            # CRUD productos (referencial)
│   └── interfaces/
│       ├── Igeneration_repository.py
│       ├── Igeneration_product_repository.py
│       ├── Icost_ledger_repository.py
│       ├── Imanager_repository.py
│       └── Iproduct_repository.py
│
├── services/                     # Orquestación de lógica de negocio
│   ├── classes/
│   │   ├── generatiion_service.py  # create() — autoriza, valida imagen, encola en Redis
│   │   └── product_service.py      # CRUD productos (referencial)
│   └── interfaces/
│       ├── Igeneratiion_service.py # Protocol: create(dto, image) → dict[idem_key, state]
│       └── Iproduct_service.py     # (referencial)
│
├── utils/                        # Utilidades específicas de una tarea
│   ├── generation_validator.py   # validate_create_generation — parseo + validación cruzada
│   ├── image_content_type.py     # Mapeo extensión → MIME type
│   ├── image_extension.py        # Validación de extensiones de imagen
│   └── image_size.py             # Validación de tamaño de imagen
│
├── worker/                       # Procesamiento asíncrono (pipeline)
│   ├── scheduler.py              # Scheduler — escanea colas FIFO, dispatchea al Worker
│   ├── worker.py                 # Worker — pipeline 8 pasos + FSM notifications (PubSub)
│   └── handler/                  # Utilidades del worker
│       └── image_loader.py       # ImageLoader — descarga con caché Redis 20min
│
├── ambassador/                   # (reservado)
│
└── main.py                       # Entry point — FastAPI app + lifespan
```

## Flujo típico

```
Request → Controller (valida DTO) → Service (orquesta) → Repository (SQL) → BD
                                                      ↕
                                               Providers (externos)
                                               Helpers (globales)
```

## Capas

- **Controller** — valida lo que llega (manualmente en multipart o con `create_validation_dependency`), llama al service, retorna respuesta estandarizada.
- **Service** — orquesta la lógica, aplica pattern result, llama a repository y/o providers.
- **Repository** — SQL (SELECT/INSERT/UPDATE/DELETE). Los nuevos repos retoran solo `bool` (creado/no creado).
- **DTO** — Pydantic models: input con `Field(..., description=...)`, output con `model_config = {"from_attributes": True}`.
- **Middleware** — `validation_middleware` inyecta DTOs validados vía dependencia; `error_handler_middleware` captura excepciones y las envuelve en `ErrorResponse`.
- **Mappers** — `to_success_response`, `to_created_response`, `to_response_with_meta`, `to_bad_request_response`, etc.
- **Providers** — wrappers de servicios externos (Redis, SeaweedFS S3, futuros LLM).
- **Helpers** — `RateLimiter` (token bucket atómico con Redis + Lua), `build_pagination_meta`.
- **Container** — Composition Root: instancia todo y expone como `container.X`.
- **Routes** — registro de routers de controllers.

## Componentes nuevos

### RateLimiter (`src/helpers/rate_limit.py`)
Token bucket atómico implementado con Redis Lua scripting (sin dependencias extra).
- **1200 fichas** por manager, refill completo en **16h** (~0.0208 ficha/s).
- Modelos: `google/gemini-3.1-flash-image-preview` = 8 fichas, `google/gemini-3-pro-image-preview` = 32 fichas.
- Operaciones atómicas vía `EVAL` — no hay condición de carrera entre requests concurrentes.
- Almacena el bucket como Redis HASH (`t`: tokens, `r`: last\_refill).
- TTL de 16h: si el manager deja de usar el sistema, el bucket se limpia solo.

Métodos:
| Método | Descripción |
|---|---|
| `manager_key_exists(key)` | `True`/`False` si el manager está cacheado |
| `get_cached_manager(key)` | Retorna el dict del manager o `None` |
| `cache_manager_key(key, data)` | Guarda datos del manager por 9h |
| `get_model_cost(model)` | Retorna costo del modelo o `HTTPException[400]` |
| `check_rate_limit(key, model)` | Consume fichas atómicamente. Retorna restantes o `HTTPException[429]` |

### Repositorios nuevos
Todos siguen el patrón: interfaz `Protocol` + clase con `session_factory`, método `create(**kwargs) → bool`.

| Repositorio | Entidad | Campos del create |
|---|---|---|
| `generation_repository` | `Generation` | manager\_id, store\_id, prompt, input\_image\_path |
| `generation_product_repository` | `GenerationProduct` | generation\_id, product\_id |
| `cost_ledger_repository` | `CostLedger` | manager\_id, store\_id, amount, currency, provider, model, tokens, ... |

### GenerationValidator (`src/utils/generation_validator.py`)
Valida el formulario multipart de creación de generación:
- Parsea `referencias` de JSON string a `list[UUID]`.
- Valida contra `CreateGenerationDTO` (Pydantic).
- Validación cruzada: `req_type=determinista` + imagen adjunta → error 400.
- Mismo formato de error que `validation_middleware`.

### GenerationService (`src/services/classes/generatiion_service.py`)
Orquesta el pipeline de creación de una generación:
1. **Autorización**: verifica cache de manager_key en Redis; si no está, busca en DB y cachea; luego cobra fichas del token bucket via `RateLimiter.authorize_and_charge()`.
2. **Validación de imagen**: si `req_type=determinista` rechaza cualquier imagen. Si hay imagen, valida extensión y tamaño, luego sube a SeaweedFS (bucket `input_images`, prefix `generations/`).
3. **Encolado**: arma payload con `idem_key` (UUID v4), datos del manager, campos del DTO (sin `manager_key`), y `input_image_path` si existe. Encola en Redis FIFO via `RedisCache.enqueue()`.
4. **Respuesta**: retorna `{"idem_key": "...", "state": "process"}`.

### RateLimiter — método nuevo
| Método | Descripción |
|---|---|
| `authorize_and_charge(key, model, manager_data=None)` | Cachea manager_data (si se provee) y consume fichas del bucket. Retorna los datos cacheados del manager. |

### Endpoint: `POST /api/v1/generations/job`
Crea una solicitud de generación.
- **Input**: multipart/form-data con `manager_key`, `prompt`, `req_type` (determinista\|abierto), `model`, `referencias` (JSON array de UUIDs), `image` (opcional, solo si type=abierto).
- **Validaciones**: DTO + cruzada (determinista no acepta imagen).
- **Respuesta**: `201 Created` con `{"idem_key": "<uuid>", "state": "process"}` envuelto en `SuccessResponse`.

### Endpoint: `GET /api/v1/generations/{idem_key}/stream`
SSE (Server-Sent Events) que sigue el progreso de una generación en tiempo real.
- **FSM**: `processing → completed | failed`
- **PubSub**: canal Redis `generation:{idem_key}`. El worker publica en cada transición.
- **Late-join**: estado final cacheado en Redis `gen_status:{idem_key}` (TTL 1h). Si el cliente llega tarde, recibe el evento final inmediatamente.
- **Cierre**: la conexión se cierra automáticamente al recibir `completed` o `failed`.
- **Respuesta**: `output_path` en `completed` (ruta SeaweedFS, no URL de descarga). `error` en `failed`.

### NanoBanana (`src/providers/classes/nano_banana.py`)
Wrapper asíncrono sobre OpenRouter para modelos Gemini de generación de imágenes.

Modelos soportados:
| Modelo | Máx imágenes |
|---|---|
| `google/gemini-3.1-flash-image-preview` | 6 |
| `google/gemini-3-pro-image-preview` | 8 |

Métodos:
| Método | Descripción |
|---|---|
| `generate(prompt, images, model)` | Toma `list[bytes]` (imágenes en memoria), las convierte a data URLs, llama a la API, decodifica la respuesta. Retorna `(list[GeneratedImage], NanoBananaInvoice)`. |
| `invoice(raw_response)` | Extrae del dict de respuesta: `usage.cost` → amount, `usage.total_tokens` → tokens, `provider`, `model`, y compone `description` con breakdown prompt/completion/image tokens. |

La detección de MIME type se hace por magic bytes (JPEG, PNG, GIF, WebP, BMP).

### ImageLoader (`src/worker/handler/image_loader.py`)
Descarga imágenes de SeaweedFS con caché Redis para evitar descargas repetidas del catálogo de productos.

- Cache key: `img_cache:{bucket}:{file_path}`
- TTL: 20 minutos
- Método: `load(bucket, file_path) → bytes`
- Flujo: Redis GET → si hit retorna; si miss → SeaweedFS GET → Redis SET → retorna

### Worker Pipeline (`src/worker/worker.py`)
Procesa un payload de generación en 8 pasos con semáforo=1 (una ejecución a la vez).

| Paso | Operación | Repo/Provider |
|---|---|---|
| 1 | INSERT generation (PENDING) | `generation_repository` |
| 2 | INSERT generation_products × N refs | `generation_product_repository` |
| 3 | UPDATE status=PROCESSING + PUBLISH | `generation_repository` + `RedisCache` |
| 4 | Cargar imágenes en memoria | `ImageLoader` (input + referencias) |
| 5 | Generar con IA | `NanoBanana.generate()` |
| 6 | Subir resultado a SeaweedFS | `SeaweedFS.upload_file()` (bucket `generation`) |
| 7 | UPDATE status=COMPLETED + output_path + PUBLISH | `generation_repository` + `RedisCache` |
| 8 | INSERT cost_ledger (invoice) | `cost_ledger_repository` |

En error en pasos 4-8 → UPDATE status=FAILED + PUBLISH.

Las notificaciones usan dos mecanismos:
1. **Redis SET** `gen_status:{idem_key}` — persistencia TTL 1h para late-join del SSE
2. **Redis PUBLISH** `generation:{idem_key}` — broadcast en tiempo real

### Scheduler (`src/worker/scheduler.py`)
Loop principal que escanea colas FIFO en Redis cada 5s.

- Descubre colas activas vía `SCAN queue:manager:*`
- Pop atómico FIFO con `delete_top()` (LPOP)
- Dispatchea al Worker (bloqueante si está ocupado por el semáforo)
- Sin pausa entre elementos: si hay trabajo pendiente, se procesa inmediatamente
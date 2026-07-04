import asyncio

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from src.conf.routes import register_routers
from src.conf.container import container
from src.conf.db import Base
from src.middlewares.error_handler_middleware import (
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)

# forzar carga de entities
import src.entities


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🔌 Probar conexión
    async with container.engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        print("✅ DB OK")

    # 🧱 Crear tablas
    async with container.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 🏁 Iniciar scheduler
    scheduler_task = asyncio.create_task(container.scheduler.run())
    print("✅ Scheduler started")

    yield

    # 🛑 Parar scheduler
    await container.scheduler.stop()
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    print("✅ Scheduler stopped")


app = FastAPI(
    title="aurora-manager",
    lifespan=lifespan,
)

# ── Exception handlers ──────────────────────────────────────────────────────
app.add_exception_handler(HTTPException,          http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception,              generic_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Hola, FastAPI está vivo 🚀"}


@app.get("/health")
async def health(db: AsyncSession = Depends(container.db_session)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}

# routes
register_routers(app)
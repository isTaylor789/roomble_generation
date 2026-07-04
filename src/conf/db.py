import os
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# engine async
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True,
)

# session async (usa async_sessionmaker, no sessionmaker)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# base para modelos
Base = declarative_base()

# dependency para FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
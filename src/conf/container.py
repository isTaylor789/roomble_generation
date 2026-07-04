import os
import boto3
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import AsyncEngine
from src.conf.db import engine, AsyncSessionLocal, get_db

# -----------    repositories --------------
from src.repositories.interfaces.Imanager_repository import IManagerRepository
from src.repositories.interfaces.Iproduct_repository import IProductRepository
from src.repositories.interfaces.Icost_ledger_repository import ICostLedgerRepository
from src.repositories.interfaces.Igeneration_product_repository import IGenerationProductRepository
from src.repositories.interfaces.Igeneration_repository import IGenerationRepository

# ----------------------
from src.repositories.classes.manager_repository import ManagerRepository
from src.repositories.classes.product_repository import ProductRepository
from src.repositories.classes.cost_ledger_repository import CostLedgerRepository
from src.repositories.classes.generation_product_repository import GenerationProductRepository
from src.repositories.classes.generation_repository import GenerationRepository


# -------------- services --------------
from src.services.classes.generatiion_service import GenerationService


# -------------- providers --------------
from src.providers.interfaces.IseaweedFS import ISeaweedFS
from src.providers.interfaces.Iredis_cache import IRedisCache
from src.providers.interfaces.Inano_banana import INanoBanana

from src.providers.classes.seaweedFS import SeaweedFS
from src.providers.classes.redis_cache import RedisCache
from src.providers.classes.nano_banana import NanoBanana

# -------------- worker / scheduler --------------
from src.worker.worker import Worker
from src.worker.scheduler import Scheduler

# -------------- helpers --------------
from src.helpers.rate_limit import RateLimiter

load_dotenv()


class Container:
    """
    Composition Root del sistema.
    TODO lo que se construya aquí es accesible al resto de la app.
    """

    def __init__(self):
        # 🌱 ENV VARS
        self.database_url: str = os.getenv("DATABASE_URL")
        self.seaweed_s3_endpoint: str = os.getenv("SEAWEED_S3_ENDPOINT", "http://localhost:8275")
        self.seaweed_s3_access_key: str = os.getenv("SEAWEED_S3_ACCESS_KEY", "local-dev")
        self.seaweed_s3_secret_key: str = os.getenv("SEAWEED_S3_SECRET_KEY", "local-dev")
        self.seaweed_s3_bucket: str = os.getenv("SEAWEED_S3_BUCKET", "datasources")
        self.redis_host: str = os.getenv("REDIS_HOST", "localhost")
        self.redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password: str | None = os.getenv("REDIS_PASSWORD")

        if not self.database_url:
            raise RuntimeError("DATABASE_URL no definida")

        # 🧱 Infraestructura
        self.engine: AsyncEngine = engine
        self.session_factory = AsyncSessionLocal
        self.db_session = get_db  # 👈 Para usar con Depends()

        # 📦 Repositories
        self.manager_repository: IManagerRepository = ManagerRepository(
            session_factory=self.session_factory
        )
        self.product_repository: IProductRepository = ProductRepository(
            session_factory=self.session_factory
        )
        self.cost_ledger_repository: ICostLedgerRepository = CostLedgerRepository(
            session_factory=self.session_factory
        )
        self.generation_product_repository: IGenerationProductRepository = GenerationProductRepository(
            session_factory=self.session_factory
        )
        self.generation_repository: IGenerationRepository = GenerationRepository(
            session_factory=self.session_factory
        )


        # 📦 Providers
        s3_client = boto3.client(
            "s3",
            endpoint_url=self.seaweed_s3_endpoint,
            aws_access_key_id=self.seaweed_s3_access_key,
            aws_secret_access_key=self.seaweed_s3_secret_key,
        )
        self.seaweed_fs: ISeaweedFS = SeaweedFS(
            s3_client=s3_client,
            default_bucket=self.seaweed_s3_bucket,
        )
        self.redis_cache: IRedisCache = RedisCache(
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
        )

        # � Helpers
        self.rate_limiter = RateLimiter(redis=self.redis_cache._client)

        # 📦 Providers (IA)
        self.nano_banana: INanoBanana = NanoBanana()

        # 🧠 Services
        self.generation_service = GenerationService(
            manager_repository=self.manager_repository,
            rate_limiter=self.rate_limiter,
            seaweed_fs=self.seaweed_fs,
            redis_cache=self.redis_cache,
        )

        # 🏭 Worker / Scheduler
        self.worker = Worker(
            generation_repository=self.generation_repository,
            generation_product_repository=self.generation_product_repository,
            product_repository=self.product_repository,
            cost_ledger_repository=self.cost_ledger_repository,
            nano_banana=self.nano_banana,
            seaweed_fs=self.seaweed_fs,
            redis_cache=self.redis_cache,
        )
        self.scheduler = Scheduler(
            redis_cache=self.redis_cache,
            worker=self.worker,
        )


# instancia única
container = Container()
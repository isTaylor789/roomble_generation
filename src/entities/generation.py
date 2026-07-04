from sqlalchemy import String, Text, ForeignKey, DateTime, func, Enum, cast
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.conf.db import Base
from src.entities.enums.generation_status import GenerationStatus
import uuid
from datetime import datetime



class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    manager_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("managers.id"), nullable=False
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False
    )
    status: Mapped[GenerationStatus] = mapped_column(
        Enum(GenerationStatus, name="generation_status", create_constraint=True),
        nullable=False,
        default=GenerationStatus.PENDING,
        server_default=cast(GenerationStatus.PENDING.value, Enum(GenerationStatus, name="generation_status"))
    )
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    output_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # relaciones
    manager = relationship("Manager", back_populates="generations")
    store = relationship("Store", back_populates="generations")
    products = relationship("GenerationProduct", back_populates="generation", cascade="all, delete-orphan")
    cost_ledger = relationship("CostLedger", back_populates="generation")

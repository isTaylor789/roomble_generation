from sqlalchemy import ForeignKey, DateTime, func, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.conf.db import Base
import uuid
from datetime import datetime 


class GenerationProduct(Base):
    __tablename__ = "generation_products"

    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


    __table_args__ = (
        PrimaryKeyConstraint("generation_id", "product_id"),
    )

    # relaciones
    generation = relationship("Generation", back_populates="products")
    product = relationship("Product", back_populates="generations")

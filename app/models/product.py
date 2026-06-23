"""
ORM models for Shopify Products and Vector Embeddings.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, Text, DateTime, func, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base_class import Base

class Product(Base):
    """
    Local cache of Shopify Products for RAG semantic search.
    Stores static data.
    """
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(255), primary_key=True) # Shopify Global ID
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    handle: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    product_type: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="")
    vendor: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    image_url: Mapped[str] = mapped_column(String(1024), nullable=True)
    
    static_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    embedding_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    embeddings: Mapped[list["ProductEmbedding"]] = relationship(
        "ProductEmbedding", back_populates="product", cascade="all, delete-orphan"
    )


class ProductEmbedding(Base):
    """
    Vector embeddings for Product chunks.
    """
    __tablename__ = "product_embeddings"
    __table_args__ = (
        Index(
            "ix_product_embedding_vector",
            "embedding_vector",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding_vector": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False, default=0)
    
    # Using 1024 dimensions as per MXBai embed model
    embedding_vector: Mapped[Vector] = mapped_column(Vector(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    product: Mapped["Product"] = relationship("Product", back_populates="embeddings")

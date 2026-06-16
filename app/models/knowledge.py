"""
ORM models for the Knowledge Base (RAG) pipeline.

Tables:
    - knowledge_base_documents: Parent documents with embedding status tracking
    - knowledge_base_chunks: Text chunks with pgvector embeddings for semantic search

Requires the pgvector PostgreSQL extension: CREATE EXTENSION vector;
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class KnowledgeBaseDocument(Base):
    """Parent document uploaded to the Knowledge Base."""

    __tablename__ = "knowledge_base_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_status: Mapped[str] = mapped_column(
        String(50),
        server_default="pending",
        nullable=False,
        comment="pending | processing | completed | failed",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=True
    )
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships
    chunks: Mapped[list["KnowledgeBaseChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<KBDocument(id={self.id}, title={self.title!r}, status={self.embedding_status!r})>"


class KnowledgeBaseChunk(Base):
    """
    Text chunk with vector embedding for semantic search.

    Uses OpenAI text-embedding-3-small (1536 dimensions) by default.
    The embedding_vector column uses pgvector's Vector type with
    HNSW indexing for fast cosine similarity queries.
    """

    __tablename__ = "knowledge_base_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_base_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_vector = mapped_column(
        Vector(1024),
        nullable=True,
        comment="Embeddings from Ollama mxbai-large (1024)",
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    document: Mapped["KnowledgeBaseDocument"] = relationship(
        back_populates="chunks"
    )

    def __repr__(self) -> str:
        return f"<KBChunk(id={self.id}, doc_id={self.document_id}, idx={self.chunk_index})>"

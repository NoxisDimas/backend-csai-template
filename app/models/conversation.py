"""
ORM models for chat operations, handoff state management, and ticketing.

Tables:
    - conversations: Parent chat threads (id = LangGraph thread_id)
    - messages: Individual chat messages with sender tracking
    - tickets: Escalation queue entries for human agents
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, Float, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.user import User


class Conversation(Base):
    """
    Parent chat thread between a customer and the AI/staff.

    The `id` (UUID) is directly mapped as `thread_id` in the
    LangGraph AsyncPostgresSaver checkpointer.

    Status transitions:
        active_ai → waiting_human → human_handling → active_ai
    """

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    anonymous_customer_id: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="active_ai",
        comment="active_ai | waiting_human | human_handling",
    )
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        server_default=func.now(), nullable=True
    )
    total_token: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    total_cost: Mapped[float] = mapped_column(
        Float, server_default="0.0", nullable=False
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="conversation",
        lazy="selectin",
    )
    assigned_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[assigned_user_id]
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, status={self.status!r})>"


class Message(Base):
    """Individual chat message within a conversation thread."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="customer | ai | staff",
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_usage: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    cost: Mapped[float] = mapped_column(
        Float, server_default="0.0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[sender_id]
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, sender={self.sender_type!r})>"


class Ticket(Base):
    """Escalation ticket created when AI hands off to human agent."""

    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[str] = mapped_column(
        String(50), server_default="medium", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50),
        server_default="open",
        nullable=False,
        comment="open | in_progress | resolved",
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    conversation: Mapped["Conversation | None"] = relationship(
        back_populates="tickets"
    )

    def __repr__(self) -> str:
        return f"<Ticket(id={self.id}, status={self.status!r})>"

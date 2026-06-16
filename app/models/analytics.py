"""
ORM models for analytics, customer feedback, and error observability.

Tables:
    - feedback: Per-conversation CSAT ratings (1-5 scale)
    - metric_snapshots: Daily aggregated dashboard metrics (cron job output)
    - error_logs: Silent error log entries dispatched to Telegram
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Feedback(Base):
    """Customer satisfaction (CSAT) rating for a conversation."""

    __tablename__ = "feedback"

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
    )
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="CSAT rating 1-5",
    )
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, rating={self.rating})>"


class MetricSnapshot(Base):
    """Daily aggregated metrics snapshot for the dashboard."""

    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(
        Date, unique=True, nullable=False, server_default=func.current_date()
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), server_default="0.0000", nullable=False
    )
    peak_hours_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    csat_average: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), server_default="0.00", nullable=False
    )
    total_conversations: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    total_tickets: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<MetricSnapshot(id={self.id}, date={self.snapshot_date})>"


class ErrorLog(Base):
    """
    Silent error log entry.

    Errors are recorded here and dispatched to the developer's Telegram
    bot without exposing raw stack traces to the frontend client.
    """

    __tablename__ = "error_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="INFO | WARNING | CRITICAL",
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    workflow_step: Mapped[str | None] = mapped_column(String(150), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    telegram_sent_status: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ErrorLog(id={self.id}, severity={self.severity!r})>"


class LLMTokenLog(Base):
    """
    Log entry for every LLM usage in the system to calculate metrics and cost accurately.
    """

    __tablename__ = "llm_token_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    prompt_tokens: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), server_default="0.000000", nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<LLMTokenLog(id={self.id}, model={self.model_name}, tokens={self.total_tokens})>"

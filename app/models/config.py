"""
ORM models for system configuration and AI persona settings.

Tables:
    - system_configs: External API keys, Shopify integration, Telegram alerts, operational hours
    - persona_settings: AI agent personality, tone, guardrail rules, OOC message
"""

from datetime import datetime

from sqlalchemy import Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class SystemConfig(Base):
    """Stores external API credentials and operational settings."""

    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shopify_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_api_token: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_secret: Mapped[str] = mapped_column(Text, nullable=False, default="")
    operational_hours_json: Mapped[dict | None] = mapped_column(
        JSONB,
        server_default='{"monday": {"start": "08:00", "end": "17:00"}}',
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SystemConfig(id={self.id}, domain={self.shopify_domain!r})>"


class PersonaSetting(Base):
    """AI agent personality and guardrail configuration."""

    __tablename__ = "persona_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tone_of_voice: Mapped[str] = mapped_column(String(100), nullable=False)
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    out_of_context_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=(
            "Maaf, saya asisten AI dari toko ini yang bertugas "
            "hanya untuk menjawab pertanyaan dengan konteks toko."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PersonaSetting(id={self.id}, name={self.persona_name!r})>"

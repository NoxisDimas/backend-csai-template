"""
Declarative base class for all SQLAlchemy ORM models.

Uses the modern SQLAlchemy 2.0 pattern with AsyncAttrs for
async-compatible attribute access and DeclarativeBase for
mapped class definitions.
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """
    Shared declarative base for all ORM models.

    AsyncAttrs enables awaitable attribute access on async sessions
    (e.g., `await instance.awaitable_attrs.relationship`).
    """

    pass


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamp columns.

    Use this on any model that needs automatic timestamping:

        class MyModel(Base, TimestampMixin):
            ...
    """

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

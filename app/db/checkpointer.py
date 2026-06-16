"""
LangGraph AsyncPostgresSaver checkpointer factory.

This module provides the infrastructure for creating the LangGraph
persistent memory checkpointer backed by PostgreSQL. The actual
agent assembly will happen in Phase 3.

Reference: langgraph.checkpoint.postgres.aio.AsyncPostgresSaver
"""

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_checkpointer_db_uri() -> str:
    """
    Get the database URI formatted for psycopg3 (LangGraph's driver).

    LangGraph's AsyncPostgresSaver uses psycopg3 directly (not SQLAlchemy),
    so we need the plain postgresql:// URI format without the asyncpg driver.
    """
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")




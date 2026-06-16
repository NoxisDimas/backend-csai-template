"""
Model import aggregator.

Importing this module ensures all ORM models are registered with
the Base.metadata, which is essential for Alembic auto-generation
to detect all tables.

This module must be imported in migrations/env.py.
"""

from app.db.base_class import Base  # noqa: F401

# Import all models so they register with Base.metadata
from app.models.config import PersonaSetting, SystemConfig  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.conversation import Conversation, Message, Ticket  # noqa: F401
from app.models.knowledge import KnowledgeBaseChunk, KnowledgeBaseDocument  # noqa: F401
from app.models.analytics import ErrorLog, Feedback, MetricSnapshot  # noqa: F401
from app.models.product import Product, ProductEmbedding  # noqa: F401

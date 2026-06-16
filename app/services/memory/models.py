"""
Pydantic models for the Mem0 memory subsystem.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    """Represents a single memory entry stored in Mem0."""

    id: str = Field(alias="id")
    user_id: str
    content: str = Field(alias="memory")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class OPMemoryClassification(BaseModel):
    """Output schema for the memory classification LLM call."""

    is_allowed: bool
    memory_type: str

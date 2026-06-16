"""
Pydantic schemas for system configuration and persona settings endpoints.

Reference: docs/api-spesification.md (Section 5: Configuration & Persona)
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PersonaSettingResponse(BaseModel):
    """Response schema for GET /config/persona."""

    id: int
    persona_name: str
    tone_of_voice: str
    rules: str | None = None
    out_of_context_message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PersonaSettingUpdate(BaseModel):
    """Request schema for PUT /config/persona."""

    persona_name: str = Field(..., min_length=1, max_length=100)
    tone_of_voice: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="e.g., 'Friendly, casual, uses emojis frequently'",
    )
    rules: str | None = Field(
        default=None,
        description="High-priority negative prompts (things the AI must never mention)",
    )
    out_of_context_message: str = Field(
        ...,
        min_length=1,
        description="Static rejection text for OOC queries",
    )


class SystemConfigResponse(BaseModel):
    """
    Response schema for GET /config/system.

    Sensitive tokens are masked for security.
    """

    id: int
    shopify_domain: str
    admin_api_token_masked: str = Field(
        description="Masked API token (e.g., shpat_****1234)"
    )
    webhook_secret_masked: str = Field(
        description="Masked Webhook Secret"
    )
    operational_hours_json: dict | None = None

    model_config = {"from_attributes": True}


class SystemConfigUpdate(BaseModel):
    """Request schema for PUT /config/system."""

    shopify_domain: str | None = Field(
        None, description="Shopify Domain (e.g., store.myshopify.com)"
    )
    admin_api_token: str | None = Field(
        None,
        description="Shopify Admin API Token (shpat_...)",
        min_length=1,
    )
    webhook_secret: str | None = Field(
        None,
        description="Shopify Webhook HMAC Secret",
        min_length=1,
    )
    operational_hours_json: dict | None = Field(
        None, description="JSON representing shop operational hours"
    )

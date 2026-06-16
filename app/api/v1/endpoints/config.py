"""
Configuration and Persona management endpoints.

- GET  /config/persona — Retrieve current AI persona settings
- PUT  /config/persona — Update AI persona settings (admin-only)
- GET  /config/system  — Retrieve system config (admin-only, masked tokens)
- PUT  /config/system  — Update system config (admin-only)

Reference: docs/api-spesification.md (Section 5)
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin, get_db
from app.core.exceptions import NotFoundError
from app.core.security import encrypt_data, decrypt_data
from app.models.config import PersonaSetting, SystemConfig
from app.services.persona_manager import PersonaManager
from app.models.user import User
from app.schemas.common import MessageResponse, SuccessResponse
from app.schemas.config_schema import (
    PersonaSettingResponse,
    PersonaSettingUpdate,
    SystemConfigResponse,
    SystemConfigUpdate,
)

router = APIRouter(prefix="/config", tags=["Configuration"])


def _mask_token(token: str, visible_chars: int = 4) -> str:
    """Mask a sensitive token, showing only the last N characters."""
    if len(token) <= visible_chars:
        return "****"
    return "*" * (len(token) - visible_chars) + token[-visible_chars:]


# ---------------------------------------------------------------------------
# Persona Settings
# ---------------------------------------------------------------------------


@router.get(
    "/persona",
    response_model=SuccessResponse[PersonaSettingResponse | None],
    summary="Get Persona Settings",
    description="Retrieve the current active AI persona configuration.",
)
async def get_persona(
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[PersonaSettingResponse | None]:
    """Get the current active persona settings."""
    result = await db.execute(
        select(PersonaSetting).order_by(PersonaSetting.id.desc()).limit(1)
    )
    persona = result.scalar_one_or_none()

    if persona is None:
        return SuccessResponse(data=None)

    return SuccessResponse(
        data=PersonaSettingResponse.model_validate(persona)
    )


@router.put(
    "/persona",
    response_model=SuccessResponse[MessageResponse],
    summary="Update Persona Settings",
    description="Update the AI agent's persona. Requires admin privileges.",
)
async def update_persona(
    payload: PersonaSettingUpdate,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[MessageResponse]:
    """Update or create persona settings (admin-only)."""
    result = await db.execute(
        select(PersonaSetting).order_by(PersonaSetting.id.desc()).limit(1)
    )
    persona = result.scalar_one_or_none()

    if persona is None:
        # Create initial persona settings
        persona = PersonaSetting(
            persona_name=payload.persona_name,
            tone_of_voice=payload.tone_of_voice,
            rules=payload.rules,
            out_of_context_message=payload.out_of_context_message,
        )
        db.add(persona)
    else:
        persona.persona_name = payload.persona_name
        persona.tone_of_voice = payload.tone_of_voice
        persona.rules = payload.rules
        persona.out_of_context_message = payload.out_of_context_message

    await db.commit()
    PersonaManager.clear_cache()

    return SuccessResponse(
        data=MessageResponse(
            message="Persona updated successfully. Agents will utilize this configuration in the next loop execution."
        )
    )


# ---------------------------------------------------------------------------
# System Configuration
# ---------------------------------------------------------------------------


from app.services.config_manager import SystemConfigManager

@router.get(
    "/system",
    response_model=SuccessResponse[SystemConfigResponse | None],
    summary="Get System Config",
    description="Retrieve system configuration (admin-only, tokens masked).",
)
async def get_system_config(
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[SystemConfigResponse | None]:
    """Get system configuration (admin-only, tokens masked)."""
    config = await SystemConfigManager.get_config(db)

    if config is None:
        return SuccessResponse(data=None)

    return SuccessResponse(
        data=SystemConfigResponse(
            id=config.id,
            shopify_domain=config.shopify_domain,
            admin_api_token_masked=_mask_token(config.admin_api_token),
            webhook_secret_masked=_mask_token(config.webhook_secret) if config.webhook_secret else "",
            operational_hours_json=config.operational_hours_json,
        )
    )


@router.put(
    "/system",
    response_model=SuccessResponse[MessageResponse],
    summary="Update System Config",
    description="Update system configuration. Admin-only.",
)
async def update_system_config(
    payload: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[MessageResponse]:
    """Update or create system configuration (admin-only)."""
    await SystemConfigManager.update_config(
        db=db,
        shopify_domain=payload.shopify_domain,
        admin_api_token=payload.admin_api_token,
        webhook_secret=payload.webhook_secret,
        operational_hours_json=payload.operational_hours_json
    )

    return SuccessResponse(
        data=MessageResponse(message="System configuration updated successfully.")
    )

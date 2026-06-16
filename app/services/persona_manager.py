from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.config import PersonaSetting
import structlog

logger = structlog.get_logger(__name__)

class PersonaManager:
    _cached_persona: dict | None = None

    @classmethod
    async def get_persona(cls, db: AsyncSession) -> dict:
        """
        Retrieves the persona settings. Uses cache if available to prevent DB queries on every message.
        """
        try:
            if cls._cached_persona is not None:
                return cls._cached_persona

            logger.info("persona_cache_miss_fetching_from_db")
            result = await db.execute(
                select(PersonaSetting).order_by(PersonaSetting.id.desc()).limit(1)
            )
            persona = result.scalar_one_or_none()

            if persona:
                cls._cached_persona = {
                    "persona_name": persona.persona_name,
                    "tone_of_voice": persona.tone_of_voice,
                    "rules": persona.rules or "",
                    "out_of_context_message": persona.out_of_context_message or "Sorry, I can only assist with store-related questions."
                }
            else:
                # Fallback default values
                cls._cached_persona = {
                    "persona_name": "CS Bestie",
                    "tone_of_voice": "Friendly and professional.",
                    "rules": "Never issue discounts without authorization.",
                    "out_of_context_message": "Sorry, I can only assist with store-related questions."
                }

            return cls._cached_persona
        except Exception as e:
            from app.services.telegram_service import log_and_alert_error_sync
            logger.error("get_persona_failed", error=str(e))
            log_and_alert_error_sync(e, "Customer Support Agent", "PersonaManager.get_persona", "Fetching persona settings")
            return {
                "persona_name": "CS Bestie",
                "tone_of_voice": "Friendly and professional.",
                "rules": "Never issue discounts without authorization.",
                "out_of_context_message": "Sorry, I can only assist with store-related questions."
            }

    @classmethod
    def clear_cache(cls):
        """Invalidate the in-memory cache."""
        logger.info("persona_cache_invalidated")
        cls._cached_persona = None

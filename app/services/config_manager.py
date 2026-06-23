from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.config import SystemConfig
from app.core.security import encrypt_data, decrypt_data
import structlog
from typing import Dict, Any, Optional

logger = structlog.get_logger(__name__)

from dataclasses import dataclass

@dataclass
class SystemConfigDTO:
    id: int
    shopify_domain: str
    admin_api_token: str
    webhook_secret: str
    operational_hours_json: Optional[Dict[str, Any]]

class SystemConfigManager:
    _cached_config: Optional[SystemConfigDTO] = None

    @classmethod
    async def get_config(cls, db: AsyncSession) -> Optional[SystemConfigDTO]:
        """
        Retrieves the system config. Uses cache if available to prevent DB queries on every message.
        """
        try:
            if cls._cached_config is not None:
                return cls._cached_config

            logger.info("system_config_cache_miss_fetching_from_db")
            result = await db.execute(
                select(SystemConfig).order_by(SystemConfig.id.desc()).limit(1)
            )
            config = result.scalar_one_or_none()

            if config:
                cls._cached_config = SystemConfigDTO(
                    id=config.id,
                    shopify_domain=config.shopify_domain,
                    admin_api_token=config.admin_api_token,
                    webhook_secret=config.webhook_secret,
                    operational_hours_json=config.operational_hours_json
                )
            else:
                cls._cached_config = None

            return cls._cached_config
        except Exception as e:
            from app.services.telegram_service import log_and_alert_error_sync
            logger.error("get_system_config_failed", error=str(e))
            log_and_alert_error_sync(e, "Customer Support Agent", "SystemConfigManager.get_config", "Fetching system config")
            return None

    @classmethod
    def clear_cache(cls):
        """Invalidate the in-memory cache."""
        logger.info("system_config_cache_invalidated")
        cls._cached_config = None

    @classmethod
    async def update_config(
        cls, 
        db: AsyncSession, 
        shopify_domain: str = None, 
        admin_api_token: str = None,
        webhook_secret: str = None,
        operational_hours_json: Dict[str, Any] = None
    ) -> SystemConfig:
        """
        Updates or creates the system config and invalidates cache.
        """
        try:
            result = await db.execute(
                select(SystemConfig).order_by(SystemConfig.id.desc()).limit(1)
            )
            config = result.scalar_one_or_none()

            if config is None:
                config = SystemConfig(
                    shopify_domain=shopify_domain,
                    admin_api_token=encrypt_data(admin_api_token) if admin_api_token else "",
                    webhook_secret=encrypt_data(webhook_secret) if webhook_secret else "",
                    operational_hours_json=operational_hours_json,
                )
                db.add(config)
            else:
                if shopify_domain is not None:
                    config.shopify_domain = shopify_domain
                if admin_api_token is not None:
                    config.admin_api_token = encrypt_data(admin_api_token)
                if webhook_secret is not None:
                    config.webhook_secret = encrypt_data(webhook_secret)
                if operational_hours_json is not None:
                    config.operational_hours_json = operational_hours_json

            await db.commit()
            await db.refresh(config)
            
            # Invalidate cache
            cls.clear_cache()
            return config
        except Exception as e:
            from app.services.telegram_service import log_and_alert_error_sync
            logger.error("update_system_config_failed", error=str(e))
            log_and_alert_error_sync(e, "Customer Support Agent", "SystemConfigManager.update_config", "Updating system config")
            raise

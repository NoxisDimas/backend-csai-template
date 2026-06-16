import redis.asyncio as redis
import structlog
from typing import Optional
from app.core.config import settings

logger = structlog.get_logger(__name__)

# Global redis client instance
_redis_client: Optional[redis.Redis] = None

async def init_redis() -> None:
    """Initialize the global Redis connection pool."""
    global _redis_client
    if _redis_client is None:
        logger.info("redis_connecting", url=settings.REDIS_URL)
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_keepalive=True
        )
        try:
            await _redis_client.ping()
            logger.info("redis_connected")
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            # Fallback or raise depending on strictness
            pass

async def close_redis() -> None:
    """Close the global Redis connection pool."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("redis_disconnected")

def get_redis() -> Optional[redis.Redis]:
    """Get the active Redis client."""
    return _redis_client

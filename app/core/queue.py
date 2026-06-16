from urllib.parse import urlparse
from typing import Optional
import structlog
from arq import create_pool
from arq.connections import RedisSettings, ArqRedis
from app.core.config import settings

logger = structlog.get_logger(__name__)

# Parse REDIS_URL to construct RedisSettings for arq
parsed_url = urlparse(settings.REDIS_URL)
# handle passwords if present
password = parsed_url.password

redis_settings = RedisSettings(
    host=parsed_url.hostname or "localhost",
    port=parsed_url.port or 6379,
    database=int((parsed_url.path or "/0").lstrip("/")),
    password=password
)

_arq_pool: Optional[ArqRedis] = None

async def init_arq() -> None:
    """Initialize the global arq connection pool."""
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(redis_settings)
        logger.info("arq_pool_initialized", host=redis_settings.host, port=redis_settings.port)

async def close_arq() -> None:
    """Close the global arq connection pool."""
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None
        logger.info("arq_pool_closed")

def get_arq_pool() -> Optional[ArqRedis]:
    """Get the active arq connection pool."""
    return _arq_pool

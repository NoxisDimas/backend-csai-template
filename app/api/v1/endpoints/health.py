"""
Health check endpoint.

Provides a quick diagnostic to verify the API is running
and can connect to the database.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.schemas.common import SuccessResponse

router = APIRouter(tags=["Health"])
logger = structlog.get_logger(__name__)

@router.get(
    "/health",
    response_model=SuccessResponse[dict],
    summary="Health Check",
    description="Verify API server and database connectivity.",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> SuccessResponse[dict]:
    """Return API and database health status."""
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "unhealthy"
        from app.services.telegram_service import log_and_alert_error
        logger.error("db_health_check_failed", error=str(e))
        await log_and_alert_error(e, "FastAPI Backend", "health_check", "Database connection check failed")

    return SuccessResponse(
        data={
            "status": "ok",
            "database": db_status,
            "service": "AI Customer Service Backend",
        }
    )

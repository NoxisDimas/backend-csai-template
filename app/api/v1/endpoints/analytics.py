from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.dependencies import get_db
from app.models.analytics import ErrorLog
from app.services.analytics_controller import AnalyticsController

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """Fetch comprehensive dashboard metrics (Tokens, CSAT, Peak Hours, etc.)."""
    controller = AnalyticsController(db)
    return await controller.get_dashboard_metrics()

@router.get("/errors")
async def get_errors(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Fetch recent silent errors."""
    result = await db.execute(
        select(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(limit)
    )
    return result.scalars().all()

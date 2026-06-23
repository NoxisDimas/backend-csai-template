from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.dependencies import get_db, get_current_admin
from app.models.analytics import ErrorLog
from app.services.analytics_controller import AnalyticsController

router = APIRouter(prefix="/analytics", tags=["Analytics"])

from app.schemas.common import SuccessResponse

@router.get(
    "/metrics", 
    response_model=SuccessResponse,
    summary="Get Dashboard Metrics",
    description="Fetch comprehensive dashboard metrics including total tokens used, CSAT average, peak hours, and estimated costs."
)
async def get_metrics(db: AsyncSession = Depends(get_db), admin = Depends(get_current_admin)):
    controller = AnalyticsController(db)
    metrics = await controller.get_dashboard_metrics()
    return SuccessResponse(data=metrics)

@router.get(
    "/errors",
    summary="Get Recent Error Logs",
    description="Fetch recent silent errors caught by the background error handler. Returns the last `limit` errors."
)
async def get_errors(limit: int = 50, db: AsyncSession = Depends(get_db), admin = Depends(get_current_admin)):
    result = await db.execute(
        select(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(limit)
    )
    return result.scalars().all()

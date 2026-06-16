"""
Analytics Controller for calculating dashboard metrics.
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract

from app.models.analytics import Feedback
from app.models.conversation import Message, Conversation

class AnalyticsController:
    """Handles complex metric aggregations and dashboard statistics."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Compile and return all dashboard metrics in a structured dictionary."""
        try:
            now = datetime.utcnow()
            today = now.date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            # 1. Total tokens (Daily, Weekly, Monthly)
            daily_tokens = await self._get_token_sum(today)
            weekly_tokens = await self._get_token_sum(week_ago)
            monthly_tokens = await self._get_token_sum(month_ago)
            
            # 2. Cost Estimation (USD only) - assume $0.0005 per 1k tokens based on monthly usage
            cost_usd = (monthly_tokens / 1000.0) * 0.0005
            
            # 3. Chat History Summary (Recent 10)
            recent_chats = await self._get_recent_chats(10)
            
            # 4. CSAT Average
            csat_avg = await self._get_csat_average()
            
            # 5. Peak Hours Heatmap
            peak_hours = await self._get_peak_hours()
            
            return {
                "tokens": {
                    "daily": daily_tokens,
                    "weekly": weekly_tokens,
                    "monthly": monthly_tokens
                },
                "cost_usd": round(cost_usd, 4),
                "chat_history": recent_chats,
                "csat_average": csat_avg,
                "peak_hours": peak_hours
            }
        except Exception as e:
            from app.services.telegram_service import log_and_alert_error_sync
            import structlog
            logger = structlog.get_logger(__name__)
            logger.error("get_dashboard_metrics_failed", error=str(e))
            log_and_alert_error_sync(e, "Customer Support Agent", "AnalyticsController.get_dashboard_metrics", "Compiling dashboard metrics")
            return {
                "tokens": {"daily": 0, "weekly": 0, "monthly": 0},
                "cost_usd": 0.0,
                "chat_history": [],
                "csat_average": 0.0,
                "peak_hours": {}
            }

    async def _get_token_sum(self, start_date: date) -> int:
        """Sum tokens used since a given date."""
        from app.models.analytics import LLMTokenLog
        query = select(func.sum(LLMTokenLog.total_tokens)).where(func.date(LLMTokenLog.created_at) >= start_date)
        result = await self.db.scalar(query)
        return int(result or 0)
        
    async def _get_recent_chats(self, limit: int) -> List[Dict[str, Any]]:
        """Fetch recent conversations along with their total token usage."""
        from app.models.analytics import LLMTokenLog
        query = select(Conversation).order_by(Conversation.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        convs = result.scalars().all()
        
        chat_summary = []
        for c in convs:
            # Match by conversation_id mapped to user_id in LLMTokenLog
            token_sum_query = select(func.sum(LLMTokenLog.total_tokens)).where(LLMTokenLog.user_id == str(c.id))
            tokens = await self.db.scalar(token_sum_query)
            
            chat_summary.append({
                "conversation_id": str(c.id),
                "status": c.status,
                "customer_id": c.anonymous_customer_id,
                "intent": c.intent,
                "created_at": c.created_at.isoformat(),
                "total_tokens": int(tokens or 0)
            })
        return chat_summary

    async def _get_csat_average(self) -> float:
        """Calculate the running average of CSAT ratings."""
        query = select(func.avg(Feedback.rating))
        result = await self.db.scalar(query)
        return round(float(result or 0.0), 2)
        
    async def _get_peak_hours(self) -> Dict[str, int]:
        """Group conversations by hour of creation."""
        query = select(
            extract('hour', Conversation.created_at).label('hour'),
            func.count(Conversation.id).label('count')
        ).group_by('hour')
        
        result = await self.db.execute(query)
        rows = result.all()
        
        heatmap = {}
        for r in rows:
            hour_str = f"{int(r.hour):02d}:00"
            heatmap[hour_str] = r.count
            
        return heatmap

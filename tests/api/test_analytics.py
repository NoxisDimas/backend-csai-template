import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_metrics(async_client: AsyncClient):
    """Test getting analytics dashboard metrics."""
    # Mock AnalyticsController.get_dashboard_metrics
    mock_metrics = {
        "total_conversations": 100,
        "total_tickets": 20,
        "total_tokens": 50000,
        "estimated_cost_usd": 0.50,
        "peak_hours": [{"time": "10:00", "count": 10}]
    }
    
    with patch("app.api.v1.endpoints.analytics.AnalyticsController.get_dashboard_metrics", return_value=mock_metrics):
        response = await async_client.get("/api/v1/analytics/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["data"]["total_conversations"] == 100

@pytest.mark.asyncio
async def test_get_errors(async_client: AsyncClient, mock_db_session):
    """Test getting error logs."""
    # Setup mock return for DB execute
    mock_result = MagicMock()
    # Mock scalars().all() -> []
    mock_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    
    response = await async_client.get("/api/v1/analytics/errors")
    
    assert response.status_code == 200
    assert response.json() == []

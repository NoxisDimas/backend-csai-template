import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check_success(async_client: AsyncClient, mock_db_session):
    """Test health check endpoint when DB is healthy."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "data" in data
    assert data["data"]["status"] == "ok"
    assert data["data"]["database"] == "healthy"

@pytest.mark.asyncio
async def test_health_check_db_failure(async_client: AsyncClient, mock_db_session):
    """Test health check endpoint when DB connection fails."""
    # Make the DB execute method raise an exception
    mock_db_session.execute.side_effect = Exception("DB Connection Error")
    
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "data" in data
    assert data["data"]["database"] == "unhealthy"

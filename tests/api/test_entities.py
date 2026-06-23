import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_kb_articles(async_client: AsyncClient, mock_db_session):
    """Test getting KB articles."""
    mock_result = MagicMock()
    # Return empty list for scalars().all()
    mock_result.scalars.return_value.all.return_value = []
    # Return 0 for count query scalar_one()
    mock_result.scalar_one.return_value = 0
    mock_db_session.execute.return_value = mock_result
    
    response = await async_client.get("/api/v1/kb/documents")
    
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"] == []

@pytest.mark.asyncio
async def test_get_products(async_client: AsyncClient, mock_db_session):
    """Test getting products."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    
    response = await async_client.get("/api/v1/products")
    
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"] == []

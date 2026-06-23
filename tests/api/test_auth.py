import uuid
import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient
from app.models.user import User
from app.core.security import hash_password

@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, mock_db_session):
    """Test successful login returns a JWT token."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash=hash_password("password123"),
        role="admin",
        name="Admin User"
    )
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_result
    
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "access_token" in data["data"]

@pytest.mark.asyncio
async def test_login_failure(async_client: AsyncClient, mock_db_session):
    """Test login fails with incorrect password."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash=hash_password("password123"),
        role="admin",
        name="Admin User"
    )
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_result
    
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"}
    )
    
    # Custom exception handlers return 401
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "AUTHENTICATION_FAILED"

@pytest.mark.asyncio
async def test_login_user_not_found(async_client: AsyncClient, mock_db_session):
    """Test login fails when user does not exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_result
    
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "password123"}
    )
    
    assert response.status_code == 401

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock

from app.main import app
from app.api.dependencies import get_db, get_current_user

@pytest.fixture(scope="session")
def anyio_backend():
    """Specify that we use asyncio for anyio."""
    return "asyncio"

@pytest.fixture
def mock_db_session():
    """Mock the AsyncSession to avoid needing a real Postgres DB."""
    session = AsyncMock()
    # Provide default behavior for scalar_one_or_none, execute, etc. if needed
    return session

@pytest.fixture
def mock_get_db(mock_db_session):
    """Override the get_db dependency."""
    async def _get_db_override():
        yield mock_db_session
    return _get_db_override

@pytest.fixture
def mock_get_current_user():
    """Override the get_current_user dependency."""
    async def _get_current_user_override():
        from app.models.user import User
        return User(id="test_admin", name="Admin", email="admin@test.com", role="superadmin", password_hash="dummy")
    return _get_current_user_override

@pytest_asyncio.fixture
async def async_client(mock_get_db, mock_get_current_user):
    """Async httpx client for testing endpoints."""
    # Override dependencies
    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    # Also we might want to override redis listener to avoid connecting to redis
    app.state.redis_listener_task = AsyncMock()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
        
    app.dependency_overrides.clear()

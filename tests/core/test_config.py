import os
from pydantic import ValidationError
import pytest
from app.core.config import Settings

def test_settings_default_loading():
    """Test that settings load correctly with default values when environment variables are missing."""
    # Temporarily remove some env variables to test defaults
    # Since DATABASE_URL and JWT_SECRET_KEY are required, we must provide them
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test_db"
    os.environ["JWT_SECRET_KEY"] = "super-secret"
    
    settings = Settings(_env_file=None)
    
    assert settings.PROJECT_NAME == "Customer Service AI"
    assert settings.APP_ENV == "development"
    assert settings.DATABASE_URL == "postgresql+asyncpg://test:test@localhost:5432/test_db"
    assert settings.database_url_sync == "postgresql://test:test@localhost:5432/test_db"

def test_settings_cors_origins_list():
    """Test the parsing of CORS_ORIGINS string into a list."""
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test_db"
    os.environ["JWT_SECRET_KEY"] = "super-secret"
    os.environ["CORS_ORIGINS"] = "http://example.com, https://example.org , "
    
    settings = Settings(_env_file=None)
    assert len(settings.cors_origins_list) == 2
    assert "http://example.com" in settings.cors_origins_list
    assert "https://example.org" in settings.cors_origins_list

def test_settings_missing_required():
    """Test that missing required variables raise a ValidationError."""
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]
    
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

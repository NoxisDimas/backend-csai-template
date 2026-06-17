"""
Centralized Configuration Module using Pydantic v2 Settings.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    PROJECT_NAME: str = Field(default="Customer Service AI", description="Name of the project")
    APP_ENV: str = Field(default="development", description="Environment: development, staging, production")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    ENCRYPTION_KEY: Optional[str] = Field(default=None, description="Fernet symmetric encryption key for DB secrets")

    # --- Database ---
    DATABASE_URL: str = Field(..., description="Async PostgreSQL connection string")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection string")

    # --- JWT Authentication ---
    JWT_SECRET_KEY: str = Field(..., description="Secret key for JWT token signing")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="JWT access token expiration time in minutes")

    # --- LLM Settings & Priority ---
    llm_priority_list: List[str] = Field(default=["openai", "groq"], description="Priority order for LLM providers")
    embed_priority_list: List[str] = Field(default=["openai", "google_genai", "ollama"], description="Priority order for Embeddings providers")

    # --- LLM Credentials ---
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API Key")
    OPENAI_CHAT_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI Chat Model")
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", description="OpenAI Embedding Model")

    GROQ_API_KEY: str = Field(default="", description="Groq API Key")
    GROQ_CHAT_MODEL: str = Field(default="llama-3.1-8b-instant", description="Groq Chat Model")

    GOOGLEGENAI_API_KEY: str = Field(default="", description="Google GenAI API Key")
    GOOGLEGENAI_CHAT_MODEL: str = Field(default="gemini-1.5-flash", description="Google GenAI Chat Model")
    GOOGLEGENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-004", description="Google GenAI Embedding Model")

    OLLAMA_BASE_URL: Optional[str] = Field(default=None, description="Ollama Base URL")
    OLLAMA_CHAT_MODEL: Optional[str] = Field(default=None, description="Ollama Chat Model")
    OLLAMA_EMBEDDING_MODEL: str = Field(default="nomic-embed-text", description="Ollama Embedding Model")

    OPENROUTER_API_KEY: str = Field(default="", description="OpenRouter API Key")
    OPENROUTER_CHAT_MODEL: str = Field(default="meta-llama/llama-3.1-8b-instruct", description="OpenRouter Chat Model")

    # --- Shopify Integration ---
    # Shopify configurations are now stored in the database

    # --- Mem0 Memory System ---
    MEM0_API_KEY: Optional[str] = Field(default=None, description="Mem0 cloud API key (optional, uses self-hosted if empty)")
    MEM0_PG_DB_NAME: str = Field(default="postgres", description="PostgreSQL database name for Mem0 vector store")
    POSTGRES_USER: str = Field(default="postgres", description="PostgreSQL user for Mem0")
    POSTGRES_PASSWORD: str = Field(default="", description="PostgreSQL password for Mem0")
    POSTGRES_HOST: str = Field(default="localhost", description="PostgreSQL host for Mem0")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port for Mem0")
    MEM0_ALLOWED_MEMORY_TYPES: List[str] = Field(
        default=["preferences", "purchase-history", "support-issues", "constraints", "persona"],
        description="Allowed memory categories for Mem0"
    )
    # --- Telemetry Credentials ---
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None, description="Telegram Bot API token")
    TELEGRAM_CHAT_ID: Optional[str] = Field(default=None, description="Telegram chat ID")
    LLM_TIMEOUT_SECONDS: float = Field(default=15.0, description="Max timeout for LLM provider in seconds")

    # --- CORS ---
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def database_url_sync(self) -> str:
        """Convert async database URL to sync for Alembic migrations."""
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    """Returns the cached settings instance."""
    return Settings()

# Alias for backwards compatibility where direct import was used
settings = get_settings()

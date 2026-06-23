"""
FastAPI Application Entry Point (App Factory Pattern).

Uses the lifespan context manager to handle startup and shutdown events:
- Startup: Initialize structured logging, verify DB connectivity
- Shutdown: Dispose database engine connections

All middleware, exception handlers, and API routers are registered here.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import CorrelationIdMiddleware
from app.db.session import engine
from app.db.checkpointer import get_checkpointer_db_uri
from app.core.redis import init_redis, close_redis
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import psycopg_pool

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    - Before yield: Startup logic (logging, DB check)
    - After yield: Shutdown cleanup (DB engine disposal)
    """
    # --- Startup ---
    setup_logging(
        json_logs=(settings.APP_ENV != "development"),
        log_level="DEBUG" if settings.DEBUG else "INFO",
    )
    logger.info(
        "application_startup",
        environment=settings.APP_ENV,
        debug=settings.DEBUG,
    )

    db_uri = get_checkpointer_db_uri()
    
    # Run setup once to create schema
    async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
        await checkpointer.setup()
        
    # Create persistent connection pool for checkpointer
    pool = psycopg_pool.AsyncConnectionPool(
        conninfo=db_uri,
        max_size=50,
        kwargs={"autocommit": True, "prepare_threshold": 0}
    )
    await pool.open()
    app.state.checkpointer_pool = pool
        
    # Initialize Redis
    await init_redis()
    
    # Initialize arq Queue Pool
    from app.core.queue import init_arq
    await init_arq()
    
    # Start Redis Pub/Sub listener
    from app.services.websocket_manager import manager
    import asyncio
    app.state.redis_listener_task = asyncio.create_task(manager.start_redis_listener())
        
    yield

    # --- Shutdown ---
    logger.info("application_shutdown")
    if hasattr(app.state, "redis_listener_task"):
        app.state.redis_listener_task.cancel()
    
    from app.core.queue import close_arq
    await close_arq()
    await close_redis()
    await pool.close()
    await engine.dispose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    tags_metadata = [
        {
            "name": "Authentication",
            "description": "Operations with user authentication and token generation. The **login** logic is here.",
        },
        {
            "name": "Knowledge Base",
            "description": "Manage the RAG documents, embeddings, and PDF uploads.",
        },
        {
            "name": "Products",
            "description": "Sync and manage Shopify product catalogs.",
        },
        {
            "name": "Chat",
            "description": "AI Chat endpoints for customers to interact with the LLM.",
        },
        {
            "name": "Conversations",
            "description": "Admin endpoints to view chat histories and metrics.",
        },
        {
            "name": "Tickets",
            "description": "Manage human escalation tickets.",
        },
        {
            "name": "Analytics",
            "description": "Fetch dashboard metrics, CSAT scores, and system errors.",
        },
    ]

    app = FastAPI(
        title="AI Customer Service API",
        description="AI-powered customer service backend for Shopify stores. Integrates LLM RAG with Shopify policies and products.",
        version="0.1.0",
        contact={
            "name": "Support Team",
            "email": "support@example.com",
        },
        license_info={
            "name": "Private/Proprietary",
        },
        openapi_tags=tags_metadata,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # --- CORS Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Correlation ID Middleware ---
    app.add_middleware(CorrelationIdMiddleware)

    # --- Exception Handlers ---
    register_exception_handlers(app)

    # --- API Routers ---
    app.include_router(api_router, prefix="/api/v1")

    # --- Prometheus Instrumentator ---
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    return app


# Application instance used by uvicorn
app = create_app()

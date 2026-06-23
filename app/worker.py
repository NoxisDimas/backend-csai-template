import structlog
from arq.connections import RedisSettings
from app.core.queue import redis_settings
from app.services.agent_orchestrator import run_agentic_loop
from app.db.session import async_session_factory as async_session_maker
from app.core.config import settings

logger = structlog.get_logger(__name__)

async def run_agent_task(ctx, conversation_id: str, message: str) -> None:
    """Task to run LangGraph logic asynchronously."""
    logger.info("running_agent_task", conversation_id=conversation_id)
    
    # We need a new db session for the worker
    async with async_session_maker() as db:
        # Re-create connection pool for checkpointer in the worker context
        import psycopg_pool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from app.db.checkpointer import get_checkpointer_db_uri
        
        db_uri = get_checkpointer_db_uri()
        async with psycopg_pool.AsyncConnectionPool(
            conninfo=db_uri,
            max_size=10,
            kwargs={"autocommit": True, "prepare_threshold": 0}
        ) as pool:
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                # run_agentic_loop handles AI generation and uses websocket_manager
                # which in turn will publish messages to Redis Pub/Sub
                await run_agentic_loop(conversation_id, message, db, checkpointer=checkpointer)

async def process_document_task(ctx, document_id: str) -> None:
    """Task to process document embeddings asynchronously."""
    import uuid
    from app.services.knowledge_service import KnowledgeService
    logger.info("running_document_task", document_id=document_id)
    doc_uuid = uuid.UUID(document_id)
    await KnowledgeService().process_document(doc_uuid)

async def send_telegram_alert_task(ctx, alert_data: dict) -> None:
    """Task to send a telegram alert asynchronously."""
    from app.services.telegram_service import send_telegram_alert_async
    logger.info("running_telegram_task")
    await send_telegram_alert_async(alert_data)


class WorkerSettings:
    """Configuration for the arq worker."""
    redis_settings = redis_settings
    functions = [run_agent_task, process_document_task, send_telegram_alert_task]
    max_jobs = 20
    max_tries = 3
    job_timeout = 300  # 5 minutes timeout for long-running LLM tasks
    
    async def on_startup(ctx):
        # We need to initialize redis for the websocket manager broadcast to work!
        from app.core.redis import init_redis
        await init_redis()
        logger.info("worker_started")
        
    async def on_shutdown(ctx):
        from app.core.redis import close_redis
        await close_redis()
        logger.info("worker_shutdown")

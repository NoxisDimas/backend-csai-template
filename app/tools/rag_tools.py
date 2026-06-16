"""
Knowledge Base retrieval tools.
"""

from langchain_core.tools import tool
from sqlalchemy import select
import structlog

from app.core.config import settings
from app.services.knowledge_service import KnowledgeService
from app.services.telegram_service import log_and_alert_error

logger = structlog.get_logger(__name__)


@tool
async def search_knowledge_base(query: str) -> str:
    """
    Search the Knowledge Base for store policies, return windows, FAQs, etc.
    Use this tool whenever the user asks a question about how the store operates.

    Args:
        query (str): The search query to find in the knowledge base.
    """
    logger.info("tool_call: search_knowledge_base", query=query)

    try:
        service = KnowledgeService()
        chunks = await service.search_knowledge_base(query, limit=3)
        
        if not chunks:
            return "No relevant information found in the knowledge base."

        context = "\n\n".join([f"Document excerpt:\n{chunk}" for chunk in chunks])
        return context

    except Exception as e:
        logger.error("rag_search_failed", error=str(e))
        await log_and_alert_error(e, "Customer Support Agent", "search_knowledge_base tool", f"Searching knowledge base for query: {query}")
        return "Sistem sedang mengalami kendala saat mencari basis pengetahuan. Mohon beri tahu pelanggan."

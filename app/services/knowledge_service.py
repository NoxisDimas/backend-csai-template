"""
Knowledge Service for abstracting pgvector RAG operations.
"""
import re
from typing import List
from uuid import UUID
import structlog
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.models_manager import LLMManager
from app.models.knowledge import KnowledgeBaseDocument, KnowledgeBaseChunk
from app.models.product import Product, ProductEmbedding
from app.db.session import async_session_factory
from app.utils.network_retry import network_retry

logger = structlog.get_logger(__name__)

class KnowledgeService:
    """
    KnowledgeService abstracts all RAG operations
    (document indexing, product indexing, and vector similarity search).
    """
    def __init__(self) -> None:
        self.embedding_semaphore = asyncio.Semaphore(3)
        self.llm_manager = LLMManager()

    @network_retry(max_retries=2, wait_seconds=1.0)
    async def _embed_query(self, text: str) -> list:
        embeddings_model = await self.llm_manager.get_static_embed_model(
            provider="ollama", embed_model="mxbai-embed-large"
        )
        return await embeddings_model.aembed_query(text)

    async def search_knowledge_base(self, query: str, limit: int = 3) -> List[str]:
        """Search the Knowledge Base chunks."""
        query_vector = await self._embed_query(query)
        async with async_session_factory() as db:
            stmt = (
                select(KnowledgeBaseChunk)
                .order_by(KnowledgeBaseChunk.embedding_vector.cosine_distance(query_vector))
                .limit(limit)
            )
            result = await db.execute(stmt)
            chunks = result.scalars().all()
            return [c.chunk_text for c in chunks]

    async def search_products(self, query: str, limit: int = 5) -> List[str]:
        """Search products and return a list of unique product IDs."""
        query_vector = await self._embed_query(query)
        async with async_session_factory() as db:
            result = await db.execute(
                select(ProductEmbedding.product_id)
                .order_by(ProductEmbedding.embedding_vector.cosine_distance(query_vector))
                .limit(limit)
            )
            product_ids = result.scalars().all()
            return list(dict.fromkeys(product_ids))  # Deduplicate

    async def process_document(self, document_id: UUID) -> None:
        """Chunk a document, generate embeddings, and save to DB."""
        async with async_session_factory() as db:
            logger.info("rag_pipeline_started", document_id=str(document_id))
            result = await db.execute(
                select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                logger.error("document_not_found", document_id=str(document_id))
                return
            
            try:
                doc.embedding_status = "processing"
                await db.commit()
                
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=500, chunk_overlap=50, separators=["\n\n", "\n", " ", ""]
                )
                texts = splitter.split_text(doc.content)
                
                embeddings_model = await self.llm_manager.get_static_embed_model(
                    provider="ollama", embed_model="mxbai-embed-large"
                )
                
                vectors = []
                batch_size = 10
                async with self.embedding_semaphore:
                    for i in range(0, len(texts), batch_size):
                        batch_texts = texts[i:i + batch_size]
                        batch_vectors = await embeddings_model.aembed_documents(batch_texts)
                        vectors.extend(batch_vectors)
                
                chunks_to_insert = []
                for i, (text, vector) in enumerate(zip(texts, vectors)):
                    chunk = KnowledgeBaseChunk(
                        document_id=doc.id, chunk_text=text, embedding_vector=vector, chunk_index=i
                    )
                    chunks_to_insert.append(chunk)
                
                db.add_all(chunks_to_insert)
                doc.embedding_status = "completed"
                await db.commit()
                logger.info("rag_pipeline_completed", document_id=str(document_id), chunks_created=len(chunks_to_insert))
            except Exception as e:
                from app.services.telegram_service import log_and_alert_error
                logger.error("rag_pipeline_failed", document_id=str(document_id), error=str(e))
                doc.embedding_status = "failed"
                await db.commit()
                await log_and_alert_error(e, "KnowledgeService", "process_document", f"Embedding document: {document_id}")
                raise e

    async def process_product_embedding(self, product_id: str) -> None:
        """Chunk a Shopify Product, generate embeddings, and save to DB."""
        def clean_text(text: str) -> str:
            if not text: return ""
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
            text = text.replace('\xa0', ' ')
            return re.sub(r'\s+', ' ', text).strip()
            
        async with async_session_factory() as db:
            logger.info("product_rag_started", product_id=product_id)
            result = await db.execute(select(Product).where(Product.id == product_id))
            product = result.scalar_one_or_none()
            if not product:
                logger.error("product_not_found", product_id=product_id)
                return
            
            try:
                product.embedding_status = "processing"
                await db.commit()
                
                content = f"Nama Produk: {clean_text(product.title)}\nKategori: {clean_text(product.product_type)}\nVendor: {clean_text(product.vendor)}\nTag: {clean_text(product.tags)}\n\nDeskripsi:\n{clean_text(product.description)}"
                texts = [content]
                
                embeddings_model = await self.llm_manager.get_static_embed_model(
                    provider="ollama", embed_model="mxbai-embed-large"
                )
                
                async with self.embedding_semaphore:
                    vectors = await embeddings_model.aembed_documents(texts)
                
                await db.execute(ProductEmbedding.__table__.delete().where(ProductEmbedding.product_id == product_id))
                
                chunks_to_insert = [
                    ProductEmbedding(product_id=product.id, chunk_text=t, embedding_vector=v, chunk_index=i)
                    for i, (t, v) in enumerate(zip(texts, vectors))
                ]
                
                db.add_all(chunks_to_insert)
                product.embedding_status = "completed"
                await db.commit()
                logger.info("product_rag_completed", product_id=product_id, chunks_created=len(chunks_to_insert))
            except Exception as e:
                from app.services.telegram_service import log_and_alert_error
                logger.error("product_rag_failed", product_id=product_id, error=str(e))
                product.embedding_status = "failed"
                await db.commit()
                await log_and_alert_error(e, "KnowledgeService", "process_product_embedding", f"Embedding product: {product_id}")
                raise e

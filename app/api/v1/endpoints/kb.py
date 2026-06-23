"""
Knowledge Base API Endpoints.
"""

import re
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
import uuid
import structlog
import io
import pandas as pd
from pypdf import PdfReader

from app.api.dependencies import get_db, get_current_user
from app.models.knowledge import KnowledgeBaseDocument, KnowledgeBaseChunk
from app.services.knowledge_service import KnowledgeService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Knowledge Base"])


# --- Schemas ---

class DocumentCreate(BaseModel):
    title: str
    content: str

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    type: str
    created_at: str
    updated_at: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    content: str


# --- Endpoints ---

@router.post(
    "/kb/documents",
    status_code=201,
    summary="Create Knowledge Base Document",
    description="Upload a new text document to the knowledge base for RAG (Retrieval-Augmented Generation)."
)
async def create_document(
    doc_in: DocumentCreate, 
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    new_doc = KnowledgeBaseDocument(
        title=doc_in.title,
        content=doc_in.content
    )
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)
    
    return {"document_id": str(new_doc.id), "status": new_doc.embedding_status}


from app.schemas.common import PaginatedResponse, ResponseMeta, PaginationMeta

def _get_doc_type(doc: KnowledgeBaseDocument) -> str:
    if doc.source_id:
        if doc.source_id.startswith("shopify_page_"):
            return "Shopify Page"
        elif doc.source_id.startswith("shopify_policy_"):
            return "Shopify Policy"
        return "Shopify Sync"
    elif doc.title:
        if doc.title.lower().endswith(".pdf"):
            return "PDF"
        elif doc.title.lower().endswith(".csv"):
            return "CSV"
        elif doc.title.lower().endswith((".xlsx", ".xls")):
            return "Excel"
    return "Text"

@router.get(
    "/kb/documents",
    response_model=PaginatedResponse[DocumentResponse],
    summary="List Documents",
    description="Fetch a paginated list of all knowledge base documents (PDFs, text, CSVs)."
)
async def list_documents(
    page: int = 1,
    size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    from sqlalchemy import func
    total_result = await db.execute(select(func.count()).select_from(KnowledgeBaseDocument))
    total_items = total_result.scalar_one()

    total_pages = (total_items + size - 1) // size
    offset = (page - 1) * size

    result = await db.execute(
        select(KnowledgeBaseDocument)
        .order_by(KnowledgeBaseDocument.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    docs = result.scalars().all()
    
    return PaginatedResponse(
        data=[
            DocumentResponse(
                id=doc.id,
                title=doc.title,
                status=doc.embedding_status,
                type=_get_doc_type(doc),
                created_at=doc.created_at.isoformat(),
                updated_at=doc.updated_at.isoformat() if doc.updated_at else None
            )
            for doc in docs
        ],
        meta=ResponseMeta(),
        pagination=PaginationMeta(
            total_items=total_items,
            total_pages=total_pages,
            current_page=page,
            per_page=size,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    )


@router.get(
    "/kb/documents/{document_id}", 
    response_model=DocumentDetailResponse,
    summary="Get Document Detail",
    description="Retrieve full details of a specific knowledge base document, including its raw text content."
)
async def get_document(
    document_id: uuid.UUID, 
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    doc = await db.get(KnowledgeBaseDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return DocumentDetailResponse(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        status=doc.embedding_status,
        type=_get_doc_type(doc),
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat() if doc.updated_at else None
    )


@router.put(
    "/kb/documents/{document_id}",
    summary="Update Document Content",
    description="Update a document's text. If content changes, it resets embedding status to pending and clears existing chunks, requiring reprocessing."
)
async def update_document(
    document_id: uuid.UUID, 
    doc_in: DocumentUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    doc = await db.get(KnowledgeBaseDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    content_changed = False
    if doc_in.title is not None:
        doc.title = doc_in.title
        
    if doc_in.content is not None and doc_in.content != doc.content:
        doc.content = doc_in.content
        doc.embedding_status = "pending"
        content_changed = True
        
    await db.commit()
    
    if content_changed:
        # Delete old chunks
        await db.execute(delete(KnowledgeBaseChunk).where(KnowledgeBaseChunk.document_id == document_id))
        await db.commit()

    return {"message": "Document updated successfully", "requires_reprocessing": content_changed}


@router.post(
    "/kb/documents/upload", 
    status_code=201,
    summary="Upload Document File",
    description="Uploads a new document file (PDF, CSV, Excel) to the knowledge base and queues it for background embedding generation."
)
async def upload_document(
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    content = ""
    filename = file.filename or "uploaded_file"
    file_bytes = await file.read()
    
    try:
        if filename.endswith(".pdf"):
            pdf_reader = PdfReader(io.BytesIO(file_bytes))
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    content += text + "\n"
        elif filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
            content = df.to_csv(index=False)
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
            content = df.to_csv(index=False)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
            
        if not content.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from file")
            
        new_doc = KnowledgeBaseDocument(
            title=filename,
            content=content.strip()
        )
        db.add(new_doc)
        await db.commit()
        await db.refresh(new_doc)
        
        # Enqueue document processing task
        from app.core.queue import get_arq_pool
        arq_pool = get_arq_pool()
        if arq_pool:
            await arq_pool.enqueue_job("process_document_task", str(new_doc.id))
        else:
            logger.warning("arq_pool_not_available_fallback_to_sync")
            from app.services.knowledge_service import KnowledgeService
            import asyncio
            asyncio.create_task(KnowledgeService().process_document(new_doc.id))
        
        return {"message": "Document uploaded successfully", "document_id": str(new_doc.id)}
        
    except Exception as e:
        logger.error("file_upload_failed", error=str(e), filename=filename)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@router.delete(
    "/kb/documents/{document_id}",
    summary="Delete Document",
    description="Delete a document and cascade delete its vector embeddings chunks."
)
async def delete_document(
    document_id: uuid.UUID, 
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    doc = await db.get(KnowledgeBaseDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    await db.delete(doc)
    await db.commit()
    
    return {"status": "success", "message": "Document deleted"}


@router.post(
    "/kb/sync-shopify-store",
    summary="Sync Shopify Store Pages",
    description="Sync Shopify store information (Pages and Policies) into the Knowledge Base automatically."
)
async def sync_shopify_store(
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    from app.services.config_manager import SystemConfigManager
    from app.core.security import decrypt_data
    import hashlib
    from app.services.shopify_controller import ShopifyController
    
    sys_config = await SystemConfigManager.get_config(db)
    if not sys_config or not sys_config.shopify_domain or not sys_config.admin_api_token:
        raise HTTPException(status_code=400, detail="Shopify configuration is missing.")
        
    controller = ShopifyController(
        domain=sys_config.shopify_domain, 
        token=decrypt_data(sys_config.admin_api_token)
    )
    
    store_info_list = await controller.get_store_information()
    sync_stats = {"new": 0, "updated": 0, "unchanged": 0}
    

    def clean_text(text: str) -> str:
        if not text:
            return ""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Remove common emojis using ranges
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
        # Replace non-breaking spaces and clean up excessive whitespace
        text = text.replace('\xa0', ' ')
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    for info in store_info_list:
        source_id = info["source_id"]
        title = clean_text(info["title"])
        content = clean_text(info["content"])
        
        # Calculate fingerprint
        fingerprint = hashlib.sha256(f"{title}|{content}".encode('utf-8')).hexdigest()
        
        # Check existing
        result = await db.execute(select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.source_id == source_id))
        existing_doc = result.scalar_one_or_none()
        
        if existing_doc:
            if existing_doc.fingerprint != fingerprint:
                existing_doc.title = title
                existing_doc.content = content
                existing_doc.fingerprint = fingerprint
                existing_doc.embedding_status = "pending"
                sync_stats["updated"] += 1
                await db.commit()
                
                from app.core.queue import get_arq_pool
                arq_pool = get_arq_pool()
                if arq_pool:
                    await arq_pool.enqueue_job("process_document_task", str(existing_doc.id))
                else:
                    background_tasks.add_task(KnowledgeService().process_document, existing_doc.id)
            else:
                sync_stats["unchanged"] += 1
        else:
            new_doc = KnowledgeBaseDocument(
                title=title,
                content=content,
                source_id=source_id,
                fingerprint=fingerprint,
                embedding_status="pending"
            )
            db.add(new_doc)
            await db.commit()
            await db.refresh(new_doc)
            sync_stats["new"] += 1
            
            from app.core.queue import get_arq_pool
            arq_pool = get_arq_pool()
            if arq_pool:
                await arq_pool.enqueue_job("process_document_task", str(new_doc.id))
            else:
                background_tasks.add_task(KnowledgeService().process_document, new_doc.id)
            
    return {
        "status": "success", 
        "data": {
            "message": f"Sync complete. New: {sync_stats['new']}, Updated: {sync_stats['updated']}, Unchanged: {sync_stats['unchanged']}"
        }
    }


@router.post(
    "/kb/documents/{document_id}/process", 
    status_code=202,
    summary="Reprocess Document Embeddings",
    description="Manually triggers the text chunking and embedding generation background task for a document."
)
async def process_kb_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    doc = await db.get(KnowledgeBaseDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    from app.core.queue import get_arq_pool
    arq_pool = get_arq_pool()
    if arq_pool:
        await arq_pool.enqueue_job("process_document_task", str(document_id))
    else:
        background_tasks.add_task(KnowledgeService().process_document, document_id)
        
    return {"message": "Embedding process started in background queue"}

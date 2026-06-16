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

from app.api.dependencies import get_db
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
    embedding_status: str
    created_at: str
    updated_at: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    content: str


# --- Endpoints ---

@router.post("/kb/documents", status_code=201)
async def create_document(doc_in: DocumentCreate, db: AsyncSession = Depends(get_db)):
    """
    Uploads a new document to the knowledge base.
    """
    new_doc = KnowledgeBaseDocument(
        title=doc_in.title,
        content=doc_in.content
    )
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)
    
    return {"document_id": str(new_doc.id), "status": new_doc.embedding_status}


@router.get("/kb/documents", response_model=List[DocumentResponse])
async def list_documents(db: AsyncSession = Depends(get_db)):
    """
    List all knowledge base documents.
    """
    result = await db.execute(select(KnowledgeBaseDocument).order_by(KnowledgeBaseDocument.created_at.desc()))
    docs = result.scalars().all()
    
    return [
        DocumentResponse(
            id=doc.id,
            title=doc.title,
            embedding_status=doc.embedding_status,
            created_at=doc.created_at.isoformat(),
            updated_at=doc.updated_at.isoformat() if doc.updated_at else None
        )
        for doc in docs
    ]


@router.get("/kb/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Get details of a specific knowledge base document including content.
    """
    doc = await db.get(KnowledgeBaseDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return DocumentDetailResponse(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        embedding_status=doc.embedding_status,
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat() if doc.updated_at else None
    )


@router.put("/kb/documents/{document_id}")
async def update_document(
    document_id: uuid.UUID, 
    doc_in: DocumentUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Update a document. If content changes, it resets embedding status to pending
    and clears existing chunks, requiring reprocessing.
    """
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


@router.post("/kb/documents/upload", status_code=201)
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Uploads a new document file (PDF, CSV, Excel) to the knowledge base.
    """
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


@router.delete("/kb/documents/{document_id}")
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Delete a document and cascade delete its chunks.
    """
    doc = await db.get(KnowledgeBaseDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    await db.delete(doc)
    await db.commit()
    
    return {"status": "success", "message": "Document deleted"}


@router.post("/kb/sync-shopify-store")
async def sync_shopify_store(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Sync Shopify store information (Pages and Policies) into Knowledge Base.
    """
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
        fingerprint = hashlib.md5(f"{title}|{content}".encode('utf-8')).hexdigest()
        
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


@router.post("/kb/documents/{document_id}/process", status_code=202)
async def process_kb_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers the text chunking and embedding generation background task.
    """
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

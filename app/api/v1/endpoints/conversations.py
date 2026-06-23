"""
Conversations & Kill-Switch API.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from sqlalchemy.orm import selectinload
from app.models.conversation import Conversation, Message
from app.models.analytics import Feedback
from app.services.websocket_manager import manager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])

from datetime import datetime

@router.get(
    "",
    summary="List Conversations",
    description="Fetch a paginated list of all conversation threads. Optionally filter by start_date and end_date."
)
async def list_conversations(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = 1,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Conversation).options(selectinload(Conversation.assigned_user))
    count_stmt = select(func.count()).select_from(Conversation)
    
    if start_date:
        stmt = stmt.where(Conversation.created_at >= start_date.replace(tzinfo=None))
        count_stmt = count_stmt.where(Conversation.created_at >= start_date.replace(tzinfo=None))
    if end_date:
        # Include the whole end day by adding time if needed, but passing ISO strings from frontend is fine.
        stmt = stmt.where(Conversation.created_at <= end_date.replace(tzinfo=None))
        count_stmt = count_stmt.where(Conversation.created_at <= end_date.replace(tzinfo=None))

    total_result = await db.execute(count_stmt)
    total_count = total_result.scalar_one()

    stmt = stmt.order_by(Conversation.last_activity_at.desc().nulls_last())
    stmt = stmt.limit(limit).offset((page - 1) * limit)

    result = await db.execute(stmt)
    return {
        "data": result.scalars().all(),
        "total": total_count,
        "page": page,
        "limit": limit
    }

@router.get(
    "/{conversation_id}/messages",
    summary="Get Conversation Messages",
    description="Fetch the complete message history for a specific conversation."
)
async def get_messages(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .options(selectinload(Message.sender_user))
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return {"data": result.scalars().all()}

@router.post(
    "/{conversation_id}/takeover",
    summary="Takeover Conversation (Kill-Switch)",
    description="Kill-Switch ON: Human staff takes over the conversation. The AI will stop responding."
)
async def takeover_conversation(
    conversation_id: uuid.UUID, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    if conv.assigned_user_id and conv.assigned_user_id != current_user.id:
        raise HTTPException(status_code=400, detail="Conversation is already being handled by another staff member.")
        
    conv.status = "human_handling"
    conv.assigned_user_id = current_user.id
    await db.commit()
    
    # Refresh to load assigned_user
    await db.refresh(conv, ['assigned_user'])
    
    # Broadcast status change to Dashboard
    await manager.broadcast_to_dashboard({
        "type": "status_update",
        "conversation_id": str(conversation_id),
        "status": "human_handling",
        "assigned_user": {"id": str(current_user.id), "name": current_user.name} if current_user else None
    })
    # Also notify the Customer
    await manager.send_to_customer(str(conversation_id), {
        "type": "status_update",
        "status": "human_handling"
    })
    
    logger.info("conversation_takeover", conversation_id=str(conversation_id), user_id=str(current_user.id))
    return {"status": "human_handling", "assigned_user": {"id": str(current_user.id), "name": current_user.name}}

@router.post(
    "/{conversation_id}/release",
    summary="Release Conversation to AI",
    description="Kill-Switch OFF: The human staff releases the conversation back to the AI for automated responses."
)
async def release_conversation(
    conversation_id: uuid.UUID, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    conv.status = "active_ai"
    conv.assigned_user_id = None
    await db.commit()
    
    # Broadcast status change to Dashboard
    await manager.broadcast_to_dashboard({
        "type": "status_update",
        "conversation_id": str(conversation_id),
        "status": "active_ai",
        "assigned_user": None
    })
    # Also notify the Customer
    await manager.send_to_customer(str(conversation_id), {
        "type": "status_update",
        "status": "active_ai"
    })
    
    logger.info("conversation_released", conversation_id=str(conversation_id))
    return {"status": "active_ai"}

from pydantic import BaseModel

class StaffMessageCreate(BaseModel):
    content: str

@router.post(
    "/{conversation_id}/messages",
    summary="Send Staff Message",
    description="Send a message as staff to the customer during a human takeover (hand-off)."
)
async def send_staff_message(
    conversation_id: uuid.UUID, 
    message: StaffMessageCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    if conv.status != "human_handling":
        raise HTTPException(status_code=400, detail="Conversation is not in human_handling status")
        
    # Save to DB
    new_message = Message(
        conversation_id=conversation_id,
        sender_type="staff",
        sender_id=current_user.id,
        content=message.content,
        cost=0.0
    )
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message, ['sender_user'])
    
    # Broadcast to Dashboard
    await manager.broadcast_to_dashboard({
        "type": "new_message",
        "conversation_id": str(conversation_id),
        "sender": "staff",
        "sender_name": current_user.name,
        "messages": message.content,
        "has_product": False,
        "products": []
    })
    
    # Send to Customer
    await manager.send_to_customer(str(conversation_id), {
        "type": "message",
        "sender": "staff",
        "sender_name": current_user.name,
        "text": message.content,
        "messages": message.content,
        "has_product": False,
        "products": []
    })
    
    return {"status": "success"}

class FeedbackCreate(BaseModel):
    rating: int
    feedback_text: str | None = None

@router.post(
    "/{conversation_id}/feedback",
    summary="Submit CSAT Feedback",
    description="Submit or update Customer Satisfaction (CSAT) feedback for a conversation."
)
async def submit_feedback(conversation_id: uuid.UUID, feedback: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    if feedback.rating < 1 or feedback.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    # Check if feedback already exists for this conversation
    result = await db.execute(select(Feedback).where(Feedback.conversation_id == conversation_id))
    existing_feedback = result.scalar_one_or_none()
    
    if existing_feedback:
        # Upsert
        existing_feedback.rating = feedback.rating
        existing_feedback.feedback_text = feedback.feedback_text
        logger.info("feedback_updated", conversation_id=str(conversation_id), rating=feedback.rating)
    else:
        # Insert
        new_feedback = Feedback(
            conversation_id=conversation_id,
            rating=feedback.rating,
            feedback_text=feedback.feedback_text
        )
        db.add(new_feedback)
        logger.info("feedback_created", conversation_id=str(conversation_id), rating=feedback.rating)
        
    await db.commit()
    
    return {"status": "success", "rating": feedback.rating}

@router.get(
    "/all-history",
    summary="Get All History Grouped",
    description="Fetch all chat history across all conversations and group them by conversation ID."
)
async def get_all_history_grouped(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message).order_by(Message.conversation_id, Message.created_at.asc())
    )
    messages = result.scalars().all()
    
    grouped_data = {}
    for msg in messages:
        conv_id = str(msg.conversation_id)
        if conv_id not in grouped_data:
            grouped_data[conv_id] = []
        grouped_data[conv_id].append({
            "id": str(msg.id),
            "sender_type": msg.sender_type,
            "content": msg.content,
            "token_usage": msg.token_usage,
            "cost": msg.cost,
            "created_at": msg.created_at,
        })
        
    return {"data": grouped_data}


"""
Conversations & Kill-Switch API.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.api.dependencies import get_db
from app.models.conversation import Conversation, Message
from app.models.analytics import Feedback
from app.services.websocket_manager import manager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])

@router.get("")
async def list_conversations(db: AsyncSession = Depends(get_db)):
    """Fetch all conversation threads."""
    result = await db.execute(
        select(Conversation).order_by(Conversation.last_activity_at.desc().nulls_last())
    )
    return result.scalars().all()

@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Fetch message history for a specific conversation."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()

@router.post("/{conversation_id}/takeover")
async def takeover_conversation(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Kill-Switch ON: Human takes over."""
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    conv.status = "human_handling"
    await db.commit()
    
    # Broadcast status change to Dashboard
    await manager.broadcast_to_dashboard({
        "type": "status_update",
        "conversation_id": str(conversation_id),
        "status": "human_handling"
    })
    # Also notify the Customer
    await manager.send_to_customer(str(conversation_id), {
        "type": "status_update",
        "status": "human_handling"
    })
    
    logger.info("conversation_takeover", conversation_id=str(conversation_id))
    return {"status": "human_handling"}

@router.post("/{conversation_id}/release")
async def release_conversation(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Kill-Switch OFF: Release back to AI."""
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    conv.status = "active_ai"
    await db.commit()
    
    # Broadcast status change to Dashboard
    await manager.broadcast_to_dashboard({
        "type": "status_update",
        "conversation_id": str(conversation_id),
        "status": "active_ai"
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

@router.post("/{conversation_id}/messages")
async def send_staff_message(conversation_id: uuid.UUID, message: StaffMessageCreate, db: AsyncSession = Depends(get_db)):
    """Send a message as staff to the customer during handoff."""
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    if conv.status != "human_handling":
        raise HTTPException(status_code=400, detail="Conversation is not in human_handling status")
        
    # Save to DB
    new_message = Message(
        conversation_id=conversation_id,
        sender_type="staff",
        content=message.content
    )
    db.add(new_message)
    await db.commit()
    
    # Broadcast to Dashboard
    await manager.broadcast_to_dashboard({
        "type": "new_message",
        "conversation_id": str(conversation_id),
        "sender": "staff",
        "messages": message.content,
        "has_product": False,
        "products": []
    })
    
    # Send to Customer
    await manager.send_to_customer(str(conversation_id), {
        "type": "new_message",
        "sender": "staff",
        "messages": message.content,
        "has_product": False,
        "products": []
    })
    
    return {"status": "success"}

class FeedbackCreate(BaseModel):
    rating: int
    feedback_text: str | None = None

@router.post("/{conversation_id}/feedback")
async def submit_feedback(conversation_id: uuid.UUID, feedback: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    """Submit CSAT feedback for a conversation (Upsert)."""
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

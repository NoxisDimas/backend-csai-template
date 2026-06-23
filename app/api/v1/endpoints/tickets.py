"""
Ticketing Management API.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
from pydantic import BaseModel

from app.api.dependencies import get_db
from app.models.conversation import Ticket

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/tickets", tags=["Tickets"])

class TicketStatusUpdate(BaseModel):
    status: str

class TicketNotesUpdate(BaseModel):
    notes: str

@router.get(
    "",
    summary="List Tickets",
    description="Fetch a list of human escalation tickets, optionally filtered by status (e.g. 'open', 'resolved')."
)
async def list_tickets(status: str = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Ticket).order_by(Ticket.created_at.desc())
    if status:
        stmt = stmt.where(Ticket.status == status)
        
    result = await db.execute(stmt)
    return {"data": result.scalars().all()}

@router.put(
    "/{ticket_id}/status",
    summary="Update Ticket Status",
    description="Update the status of a human escalation ticket."
)
async def update_ticket_status(ticket_id: uuid.UUID, payload: TicketStatusUpdate, db: AsyncSession = Depends(get_db)):
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    ticket.status = payload.status
    await db.commit()
    
    logger.info("ticket_status_updated", ticket_id=str(ticket_id), status=payload.status)
    return {"id": str(ticket_id), "status": ticket.status}

@router.put(
    "/{ticket_id}/notes",
    summary="Update Ticket Notes",
    description="Update or append internal notes for a human escalation ticket."
)
async def update_ticket_notes(ticket_id: uuid.UUID, payload: TicketNotesUpdate, db: AsyncSession = Depends(get_db)):
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    ticket.notes = payload.notes
    await db.commit()
    
    logger.info("ticket_notes_updated", ticket_id=str(ticket_id))
    return {"id": str(ticket_id), "notes": ticket.notes}

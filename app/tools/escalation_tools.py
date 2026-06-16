"""
Escalation tools for human handoff.
"""

from langchain_core.tools import tool
import structlog
import uuid
from app.db.session import async_session_factory
from app.models.conversation import Conversation, Ticket
from sqlalchemy import update
from app.services.telegram_service import log_and_alert_error

logger = structlog.get_logger(__name__)

def create_escalation_tools(conversation_id: str) -> list:
    @tool
    async def escalate_to_human(reason: str) -> str:
        """
        Escalates the current conversation to a human customer support agent.
        Use this when the customer is angry, asks for a human, or the request is too complex.
        
        Args:
            reason (str): The reason for escalation.
        """
        logger.info("tool_call: escalate_to_human", conversation_id=conversation_id, reason=reason)
        
        try:
            conv_uuid = uuid.UUID(conversation_id)
            
            async with async_session_factory() as session:
                # 1. Update conversation status to waiting_human
                await session.execute(
                    update(Conversation)
                    .where(Conversation.id == conv_uuid)
                    .values(status="waiting_human")
                )
                
                # 2. Create a new Ticket
                new_ticket = Ticket(
                    conversation_id=conv_uuid,
                    category="escalation",
                    priority="high",
                    status="open",
                    notes=f"Escalation Triggered by AI.\nReason: {reason}"
                )
                session.add(new_ticket)
                await session.commit()
                
                logger.info("ticket_created_successfully", ticket_id=str(new_ticket.id))
                
        except Exception as e:
            logger.error("escalation_failed", error=str(e))
            await log_and_alert_error(e, "Customer Support Agent", "escalate_to_human tool", f"Escalating reason: {reason}", conversation_id)
            return "Sistem sedang mengalami kendala saat eskalasi ke staf. Mohon beri tahu pelanggan."

        return (
            "Successfully escalated to a human agent. Please inform the customer "
            "that a support ticket has been created and an agent will be with them shortly."
        )

    return [escalate_to_human]

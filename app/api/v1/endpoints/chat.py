"""
WebSocket Endpoints for Custom Chatbubble.
"""

import uuid
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.session import async_session_factory as async_session_maker
from app.services.agent_orchestrator import run_agentic_loop
from app.models.conversation import Conversation, Message
from app.services.persona_manager import PersonaManager
from app.services.websocket_manager import manager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.websocket("/ws/{conversation_id}")
async def chat_websocket(
    websocket: WebSocket,
    conversation_id: str
):
    """
    WebSocket endpoint for the Custom Chatbubble.
    Maintains a persistent connection for real-time bidirectional messaging.
    """
    await manager.connect_customer(websocket, conversation_id)
    
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        logger.warning("invalid_uuid_websocket", conversation_id=conversation_id)
        await websocket.close(code=1003)
        return
        
    try:
        # Create a short-lived session to fetch/create the conversation initially
        async with async_session_maker() as db:
            conv = await db.get(Conversation, conv_uuid)
            if not conv:
                conv = Conversation(id=conv_uuid, anonymous_customer_id="web_customer")
                db.add(conv)
                try:
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    if "UniqueViolationError" in str(e) or "conversations_pkey" in str(e):
                        logger.info("conversation_already_exists_race_condition", conversation_id=conversation_id)
                    else:
                        raise e

                
        # Enter the message loop
        import json
        while True:
            # Receive text from chatbubble
            raw_data = await websocket.receive_text()
            logger.info("websocket_message_received", conversation_id=conversation_id)
            
            # Parse JSON to get plain text
            try:
                parsed_data = json.loads(raw_data)
                # Fallback to raw_data if 'text' isn't in JSON
                customer_text = parsed_data.get("text", raw_data)
            except Exception:
                customer_text = raw_data
            
            # Use a fresh database session for each message to avoid stale connections
            async with async_session_maker() as db:
                # Re-fetch conversation to check status
                conv = await db.get(Conversation, conv_uuid)
                
                # Save customer message to DB
                new_message = Message(
                    conversation_id=conv_uuid,
                    sender_type="customer",
                    content=customer_text,
                    cost=0.0
                )
                db.add(new_message)
                await db.commit()
                
                # Broadcast to Dashboard
                await manager.broadcast_to_dashboard({
                    "type": "new_message",
                    "conversation_id": conversation_id,
                    "sender": "customer",
                    "messages": customer_text,
                    "has_product": False,
                    "products": []
                })
                
                # Kill-Switch Check (human_handling)
                if conv.status == "human_handling":
                    logger.info("kill_switch_active_skipping_ai", conversation_id=conversation_id)
                    # Let the human handle it via Dashboard, no AI reply.
                    continue
                    
                # Retrieve active Persona Settings (uses cache if available)
                persona = await PersonaManager.get_persona(db)
                persona_rules = persona["rules"]
                ooc_fallback_msg = persona["out_of_context_message"]

                # Send typing indicator before AI starts processing
                typing_payload = {
                    "type": "typing",
                    "status": True,
                    "conversation_id": conversation_id
                }
                await manager.send_to_customer(conversation_id, typing_payload)
                await manager.broadcast_to_dashboard(typing_payload)

                # Enqueue the LangGraph AI loop to the arq Worker Pool
                from app.core.queue import get_arq_pool
                try:
                    arq_pool = get_arq_pool()
                    if arq_pool:
                        await arq_pool.enqueue_job("run_agent_task", conversation_id, customer_text)
                        logger.info("enqueued_agent_task", conversation_id=conversation_id)
                    else:
                        logger.warning("arq_pool_not_available_fallback_to_sync")
                        # Fallback to sync execution if queue is not available
                        pool = getattr(websocket.app.state, "checkpointer_pool", None)
                        if pool:
                            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                            async with pool.connection() as conn:
                                checkpointer = AsyncPostgresSaver(conn)
                                await run_agentic_loop(conversation_id, customer_text, db, checkpointer=checkpointer)
                        else:
                            await run_agentic_loop(conversation_id, customer_text, db, checkpointer=None)
                except Exception as e:
                    logger.error("enqueue_task_failed", error=str(e))
                    await manager.send_to_customer(conversation_id, {"messages": "Terjadi kesalahan internal (Redis Timeout). Sistem sedang memulihkan diri, silakan coba beberapa saat lagi."})
            
    except (WebSocketDisconnect, RuntimeError) as e:
        logger.info("websocket_disconnected", conversation_id=conversation_id, reason=str(e))
        manager.disconnect_customer(websocket, conversation_id)
    except Exception as e:
        logger.exception("websocket_error", conversation_id=conversation_id, error=str(e))
        manager.disconnect_customer(websocket, conversation_id)

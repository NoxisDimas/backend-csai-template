"""
WebSocket Live Inbox Route.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

from app.services.websocket_manager import manager

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Live Inbox"])

@router.websocket("/ws/inbox")
async def websocket_inbox(websocket: WebSocket):
    """
    WebSocket endpoint for dashboard clients to receive real-time updates.
    """
    await manager.connect_dashboard(websocket)
    try:
        while True:
            # Keep connection open and listen for pings/messages from client
            data = await websocket.receive_text()
            logger.debug("websocket_client_message", data=data)
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)

"""
WebSocket Connection Manager for Custom Chatbubble & Dashboard.
"""

from typing import List, Dict, Any
from fastapi import WebSocket
import structlog

logger = structlog.get_logger(__name__)

import asyncio
import json
from app.core.redis import get_redis

class ConnectionManager:
    def __init__(self):
        # Dashboard connections receive global updates
        self.dashboard_connections: List[WebSocket] = []
        # Customer connections receive only messages for their conversation
        self.customer_connections: Dict[str, List[WebSocket]] = {}
        self._listener_task = None

    async def start_redis_listener(self):
        """Background task to listen for Redis Pub/Sub messages."""
        while True:
            try:
                redis_client = get_redis()
                if not redis_client:
                    logger.warning("redis_not_available_for_pubsub")
                    await asyncio.sleep(5)
                    continue

                pubsub = redis_client.pubsub()
                await pubsub.subscribe("channel:dashboard", "channel:customer")
                
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message["type"] == "message":
                        channel = message["channel"]
                        data = json.loads(message["data"])
                        
                        if channel == "channel:dashboard":
                            await self._local_broadcast_to_dashboard(data)
                        elif channel == "channel:customer":
                            conversation_id = data.get("conversation_id")
                            payload = data.get("payload")
                            if conversation_id and payload:
                                await self._local_send_to_customer(conversation_id, payload)
                    await asyncio.sleep(0.01)
                                
            except asyncio.CancelledError:
                if 'pubsub' in locals():
                    await pubsub.unsubscribe()
                break
            except Exception as e:
                if "Timeout" in str(e):
                    # Ignore read timeouts and continue listening
                    await asyncio.sleep(0.1)
                    continue
                logger.error("redis_listener_failed_reconnecting", error=str(e))
                await asyncio.sleep(3)

    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboard_connections.append(websocket)
        logger.info("dashboard_websocket_connected", total_connections=len(self.dashboard_connections))

    def disconnect_dashboard(self, websocket: WebSocket):
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)
            logger.info("dashboard_websocket_disconnected", total_connections=len(self.dashboard_connections))

    async def connect_customer(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        if conversation_id not in self.customer_connections:
            self.customer_connections[conversation_id] = []
        self.customer_connections[conversation_id].append(websocket)
        logger.info("customer_websocket_connected", conversation_id=conversation_id)

    def disconnect_customer(self, websocket: WebSocket, conversation_id: str):
        if conversation_id in self.customer_connections:
            if websocket in self.customer_connections[conversation_id]:
                self.customer_connections[conversation_id].remove(websocket)
            if not self.customer_connections[conversation_id]:
                del self.customer_connections[conversation_id]
            logger.info("customer_websocket_disconnected", conversation_id=conversation_id)

    async def broadcast_to_dashboard(self, message: Dict[str, Any]):
        """Publish a message to all dashboard connections via Redis."""
        redis_client = get_redis()
        if redis_client:
            await redis_client.publish("channel:dashboard", json.dumps(message))
        else:
            await self._local_broadcast_to_dashboard(message)

    async def _local_broadcast_to_dashboard(self, message: Dict[str, Any]):
        if not self.dashboard_connections:
            return
            
        disconnected = []
        for connection in self.dashboard_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                exc_type = type(e).__name__
                if exc_type in ("WebSocketDisconnect", "ConnectionClosedError", "ConnectionClosedOK", "ClientDisconnected", "RuntimeError"):
                    logger.info("dashboard_websocket_disconnected_during_send")
                else:
                    from app.services.telegram_service import log_and_alert_error
                    logger.warning("dashboard_broadcast_failed", error=str(e))
                disconnected.append(connection)
                
        for conn in disconnected:
            self.disconnect_dashboard(conn)

    async def send_to_customer(self, conversation_id: str, message: Dict[str, Any]):
        """Publish a message to a specific customer's conversation via Redis."""
        redis_client = get_redis()
        if redis_client:
            payload = {
                "conversation_id": conversation_id,
                "payload": message
            }
            await redis_client.publish("channel:customer", json.dumps(payload))
        else:
            await self._local_send_to_customer(conversation_id, message)

    async def _local_send_to_customer(self, conversation_id: str, message: Dict[str, Any]):
        if conversation_id not in self.customer_connections:
            return
            
        disconnected = []
        for connection in self.customer_connections[conversation_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                exc_type = type(e).__name__
                if exc_type in ("WebSocketDisconnect", "ConnectionClosedError", "ConnectionClosedOK", "ClientDisconnected", "RuntimeError"):
                    logger.info("customer_websocket_disconnected_during_send", conversation_id=conversation_id)
                else:
                    import traceback
                    from app.services.telegram_service import log_and_alert_error
                    logger.warning("customer_send_failed", conversation_id=conversation_id, error=str(e), traceback=traceback.format_exc())
                disconnected.append(connection)
                
        for conn in disconnected:
            self.disconnect_customer(conn, conversation_id)

manager = ConnectionManager()


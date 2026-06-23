"""
Telegram Alert Engine.
"""

import asyncio
import structlog
import httpx

from app.core.config import get_settings
from app.utils.network_retry import network_retry

import traceback
from datetime import datetime
from typing import Optional, TypedDict

logger = structlog.get_logger(__name__)

class TelegramAlertPayload(TypedDict, total=False):
    project_name: str
    service: str
    environment: str
    request_id: str
    user_id: str
    session_id: str
    agent_name: str
    node_name: str
    error_message: str
    error_type : str
    affected_action: str
    next_action: str
    traceback_str: str

@network_retry(max_retries=3, wait_seconds=2.0)
async def _post_telegram(url: str, payload: dict) -> None:
    """Send a POST request to the Telegram API with retry."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        logger.info("telegram_alert_sent", status_code=response.status_code)


async def send_telegram_alert_async(alert_data: TelegramAlertPayload) -> None:
    """
    Sends an alert message to the developer's Telegram chat asynchronously.
    Fails silently if the token/chat_id is missing or network fails.
    """
    settings = get_settings()
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.debug("telegram_alert_skipped", reason="missing_credentials")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    import html
    
    # Set default values
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    error_msg = html.escape(str(alert_data.get('error_message', 'Unknown Error')))
    tb_str = html.escape(str(alert_data.get('traceback_str', 'No traceback provided')))
    
    message_lines = [
        "🚨 <b>CRITICAL ERROR</b>",
        "",
        f"<b>Project Name</b> : {html.escape(str(alert_data.get('project_name', settings.PROJECT_NAME)))}",
        f"<b>Service</b> : {html.escape(str(alert_data.get('service', 'Customer Support Agent')))}",
        f"<b>Environment</b> : {html.escape(str(alert_data.get('environment', 'Production')))}",
        "",
        f"<b>Time</b> : {now_str}",
        f"<b>Request ID</b> : {html.escape(str(alert_data.get('request_id', 'N/A')))}",
        "",
        f"<b>User ID</b> : {html.escape(str(alert_data.get('user_id', 'N/A')))}",
        f"<b>Session ID</b> : {html.escape(str(alert_data.get('session_id', 'N/A')))}",
        "",
        f"<b>Agent</b> : {html.escape(str(alert_data.get('agent_name', 'Customer Support Agent')))}",
        f"<b>Node</b> : {html.escape(str(alert_data.get('node_name', 'N/A')))}",
        "",
        f"<b>Error Type</b> : {html.escape(str(alert_data.get('error_type', 'Exception')))}",
        f"<b>Error Message</b> :\n<code>{error_msg}</code>",
        "",
        f"<b>Affected Action</b> :\n{html.escape(str(alert_data.get('affected_action', 'N/A')))}",
        "",
        f"<b>Next Action</b> :\n{html.escape(str(alert_data.get('next_action', '- Please check logs')))}",
        "",
        "<b>Traceback</b> :",
        f"<pre>{tb_str}</pre>"
    ]
    
    text_message = "\n".join(message_lines)
    
    # Telegram max length is 4096. Truncate safely.
    if len(text_message) > 4000:
        text_message = text_message[:3980] + "\n...[TRUNCATED]</pre>"

    payload = {
        "chat_id": chat_id,
        "text": text_message,
        "parse_mode": "HTML",
    }

    try:
        await _post_telegram(url, payload)
    except Exception as e:
        logger.warning("telegram_alert_failed", error=str(e))


import uuid
from app.db.session import async_session_factory
from app.models.analytics import ErrorLog

def fire_telegram_alert(alert_data: TelegramAlertPayload) -> None:
    """
    Fire and forget helper to schedule the async alert.
    """
    try:
        from app.core.queue import get_arq_pool
        arq_pool = get_arq_pool()
        if arq_pool:
            loop = asyncio.get_running_loop()
            loop.create_task(arq_pool.enqueue_job("send_telegram_alert_task", dict(alert_data)))
            return
    except Exception as e:
        logger.warning("failed_to_enqueue_telegram_alert", error=str(e))

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_telegram_alert_async(alert_data))
    except RuntimeError:
        asyncio.run(send_telegram_alert_async(alert_data))

async def log_and_alert_error(
    e: Exception, 
    service: str, 
    node: str, 
    action: str, 
    conversation_id: str = "N/A"
) -> None:
    """
    Centralized error handler.
    1. Grabs its own DB session to save the ErrorLog.
    2. Dispatches a detailed Telegram alert.
    """
    tb_str = traceback.format_exc()
    
    # Fire Telegram Alert
    payload = TelegramAlertPayload(
        service=service,
        environment="Production",
        request_id=f"req_{uuid.uuid4().hex[:6]}",
        user_id="System",
        session_id=conversation_id,
        agent_name=service,
        node_name=node,
        error_type=type(e).__name__,
        error_message=str(e),
        affected_action=action,
        next_action="- Verify error context\n- Review logs",
        traceback_str=tb_str
    )
    fire_telegram_alert(payload)
    
    # Save to ErrorLog DB safely
    try:
        async with async_session_factory() as session:
            error_log = ErrorLog(
                severity="CRITICAL",
                category=service,
                workflow_step=node,
                error_message=str(e) + f"\n\nTraceback:\n{tb_str}",
                conversation_id=uuid.UUID(conversation_id) if conversation_id != "N/A" else None,
                telegram_sent_status=True
            )
            session.add(error_log)
            await session.commit()
    except Exception as db_err:
        logger.error("failed_to_save_error_log", error=str(db_err))

def log_and_alert_error_sync(
    e: Exception, 
    service: str, 
    node: str, 
    action: str, 
    conversation_id: str = "N/A"
) -> None:
    """Synchronous wrapper for log_and_alert_error."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(log_and_alert_error(e, service, node, action, conversation_id))
    except RuntimeError:
        asyncio.run(log_and_alert_error(e, service, node, action, conversation_id))


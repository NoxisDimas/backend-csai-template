import re
from typing import Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage

class SafetyAndEscalationMiddleware(AgentMiddleware):
    """
    Middleware custom untuk mendeteksi permintaan eskalasi eksplisit atau
    kata-kata kasar dari pengguna. Jika terdeteksi, middleware ini akan
    secara instan memotong jalur ke LLM (zero token, zero latency)
    dan langsung mengembalikan pesan eskalasi.
    """
    def __init__(self, ooc_message: str = "Saya memahami kekhawatiran Anda. Saya akan menyambungkan Anda dengan agen manusia kami untuk bantuan lebih lanjut."):
        super().__init__()
        self.ooc_message = ooc_message
        # Pattern untuk kata-kata kasar atau permintaan agen manusia
        self.escalation_pattern = re.compile(
            r"\b(fuck|shit|lawsuit|tuntut|complain|komplain|human agent|agen manusia|bicara dengan manager|speak to a manager)\b",
            re.IGNORECASE
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        try:
            # Periksa pesan terakhir (pesan dari pengguna)
            messages = request.state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if last_msg.type == "human":
                    content = str(last_msg.content).lower()
                    # Jika terdeteksi kata eskalasi, bypass LLM
                    if self.escalation_pattern.search(content):
                        return ModelResponse(
                            result=[AIMessage(content=self.ooc_message)]
                        )
            
            # Jika tidak, teruskan request ke LLM (handler)
            return handler(request)
        except Exception as e:
            from app.services.telegram_service import log_and_alert_error_sync
            import structlog
            logger = structlog.get_logger(__name__)
            logger.error("middleware_sync_failed", error=str(e))
            log_and_alert_error_sync(e, "Customer Support Agent", "SafetyAndEscalationMiddleware", "Processing sync message")
            return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable,
    ) -> ModelResponse:
        try:
            # Periksa pesan terakhir (pesan dari pengguna)
            messages = request.state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if last_msg.type == "human":
                    content = str(last_msg.content).lower().strip()
                    # Jika terdeteksi kata eskalasi, bypass LLM
                    if self.escalation_pattern.search(content):
                        return ModelResponse(
                            result=[AIMessage(content=self.ooc_message)]
                        )
                    
                    # Cek Redis FAQ / OOC Cache
                    try:
                        from app.core.redis import get_redis
                        redis_client = get_redis()
                        if redis_client:
                            # Gunakan content sebagai kunci pencarian cache
                            cached_reply = await redis_client.get(f"faq:{content}")
                            if cached_reply:
                                import structlog
                                structlog.get_logger(__name__).info("faq_cache_hit", query=content)
                                return ModelResponse(
                                    result=[AIMessage(content=cached_reply)]
                                )
                    except Exception as cache_err:
                        import structlog
                        structlog.get_logger(__name__).warning("faq_cache_error", error=str(cache_err))
            
            # Jika tidak, teruskan request ke LLM (handler) secara async
            return await handler(request)
        except Exception as e:
            from app.services.telegram_service import log_and_alert_error_sync
            import structlog
            logger = structlog.get_logger(__name__)
            logger.error("middleware_async_failed", error=str(e))
            log_and_alert_error_sync(e, "Customer Support Agent", "SafetyAndEscalationMiddleware", "Processing async message")
            return await handler(request)

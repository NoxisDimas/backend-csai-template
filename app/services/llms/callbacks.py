"""
Global Cost Handler for asynchronous LangChain token cost tracking.
"""

import logging
from typing import Any, Dict

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

# Prices per 1000 tokens in USD
PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "gemini-1.5-flash": {"prompt": 0.000075, "completion": 0.0003},
    "gemini-1.5-pro": {"prompt": 0.00125, "completion": 0.005},
    "llama3-8b-8192": {"prompt": 0.00005, "completion": 0.00008},
}

class GlobalCostHandler(AsyncCallbackHandler):
    """
    Asynchronous callback handler to track token expenditures
    and estimate costs for each LLM response.
    """

    def __init__(self, user_id: str, channel: str) -> None:
        super().__init__()
        self.user_id = user_id
        self.channel = channel

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: str,
        parent_run_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Extract token usage and calculate estimated cost asynchronously.
        Fail silently on exception to preserve the end-user experience.
        """
        try:
            if not response.llm_output:
                return

            token_usage: Dict[str, Any] = response.llm_output.get("token_usage", {})
            if not token_usage:
                return

            prompt_tokens: int = token_usage.get("prompt_tokens", 0)
            completion_tokens: int = token_usage.get("completion_tokens", 0)
            total_tokens: int = token_usage.get("total_tokens", 0)
            
            model_name: str = response.llm_output.get("model_name", "unknown")
            
            estimated_cost: float = 0.0
            pricing: Dict[str, float] | None = PRICING.get(model_name)
            
            if pricing:
                cost_prompt = (prompt_tokens / 1000) * pricing["prompt"]
                cost_completion = (completion_tokens / 1000) * pricing["completion"]
                estimated_cost = cost_prompt + cost_completion

            # Write results to structured logging (JSON format expected by backend)
            logger.info(
                "llm_cost_tracking",
                extra={
                    "user_id": self.user_id,
                    "channel": self.channel,
                    "run_id": str(run_id),
                    "model_name": model_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "estimated_cost_usd": round(estimated_cost, 6)
                }
            )

            # Persist the token usage to the database
            from app.db.session import async_session_factory
            from app.models.analytics import LLMTokenLog

            async with async_session_factory() as session:
                new_log = LLMTokenLog(
                    run_id=str(run_id),
                    user_id=self.user_id,
                    channel=self.channel,
                    model_name=model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated_cost_usd=estimated_cost
                )
                session.add(new_log)
                await session.commit()

        except Exception as e:
            # Silent failure: ensures no technical noise for customers
            logger.warning("cost_tracking_failed", extra={"error": str(e)})

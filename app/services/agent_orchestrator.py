"""
LangGraph Agent Orchestrator.
"""

from typing import Dict, Any, List, TypedDict
import uuid
import traceback
from langchain.agents import create_agent
from langchain.agents.middleware import PIIMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from app.services.persona_manager import PersonaManager
from app.models.config import SystemConfig
from app.models.analytics import ErrorLog
from app.services.telegram_service import fire_telegram_alert, TelegramAlertPayload
from sqlalchemy import select
from app.tools.guardrails import is_within_operational_hours

from app.core.config import get_settings
from app.core.security import decrypt_data
from app.services.models_manager import LLMManager
from app.services.shopify_controller import ShopifyController
from app.tools.shopify_tools import (
    create_order_lookup_tools,
    create_search_product_tools,
    create_shopify_shop_info_tools,
    create_discount_tools
)
from app.tools.rag_tools import search_knowledge_base
from app.tools.escalation_tools import create_escalation_tools
from app.models.conversation import Message
from app.services.websocket_manager import manager

logger = structlog.get_logger(__name__)
settings = get_settings()

class ProductInfo(TypedDict):
    title: str
    url: str
    image_url: str
    price: str

class AgentResponseFormat(TypedDict):
    messages: str
    has_product: bool
    products: List[ProductInfo]

async def _build_tools(conversation_id: str, sys_config: Any = None) -> list:
    """Assemble the full tool list from all factory modules."""
    domain = sys_config.shopify_domain if sys_config else None
    token = decrypt_data(sys_config.admin_api_token) if sys_config and sys_config.admin_api_token else None
    shopify_ctrl = ShopifyController(domain=domain, token=token)

    tools = [
        *create_order_lookup_tools(shopify_ctrl),
        *create_search_product_tools(shopify_ctrl),
        *create_shopify_shop_info_tools(shopify_ctrl),
        *create_discount_tools(shopify_ctrl),
        # RAG & Escalation
        search_knowledge_base,
        *create_escalation_tools(conversation_id),
    ]
    return tools


async def _handle_agent_error(db: AsyncSession, conversation_id: str, e: Exception, node_name: str, affected_action: str):
    tb_str = traceback.format_exc()
    
    # 1. Fire Telegram Alert
    payload = TelegramAlertPayload(
        service="Customer Support Agent",
        environment="Production",
        request_id=f"req_{uuid.uuid4().hex[:6]}",
        user_id="N/A",
        session_id=conversation_id,
        agent_name="Main Conversational Agent",
        node_name=node_name,
        error_type=type(e).__name__,
        error_message=str(e),
        affected_action=affected_action,
        next_action="- Check logs for recent deployments\n- Verify API tokens/network",
        traceback_str=tb_str
    )
    fire_telegram_alert(payload)
    
    # 2. Save to ErrorLog DB
    try:
        error_log = ErrorLog(
            severity="CRITICAL",
            category="Agent Execution",
            workflow_step=node_name,
            error_message=str(e) + f"\n\nTraceback:\n{tb_str}",
            conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
            telegram_sent_status=True
        )
        db.add(error_log)
        await db.commit()
    except Exception as db_err:
        logger.error("failed_to_save_error_log", error=str(db_err))

async def run_agentic_loop(
    conversation_id: str,
    message: str,
    db: AsyncSession,
    checkpointer: Any = None,
) -> str:
    """
    Assembles the LangChain agent, injects persona, and executes the loop.
    Uses the LLMManager to dynamically fetch the model per session for accurate cost tracking.
    """
    logger.info("agentic_loop_started", conversation_id=conversation_id)

    # Fetch active Persona Settings (uses cache if available)
    persona = await PersonaManager.get_persona(db)
    persona_name = persona["persona_name"]
    tone_of_voice = persona["tone_of_voice"]
    rules = persona["rules"]

    # Fetch System Config for Operational Hours
    from app.services.config_manager import SystemConfigManager
    sys_config = await SystemConfigManager.get_config(db)
    
    op_hours_context = "Store is operational."
    if sys_config and sys_config.operational_hours_json:
        try:
            # sys_config.operational_hours_json may be a dict if parsed by SQLAlchemy JSONB
            # Ensure we pass it directly
            if is_within_operational_hours(sys_config.operational_hours_json):
                op_hours_context = "The store is currently OPEN (within operational hours)."
            else:
                op_hours_context = "The store is currently CLOSED (outside operational hours). IMPORTANT: If you escalate to a human, YOU MUST inform the customer that their ticket will be handled tomorrow during work hours."
        except Exception as e:
            logger.warning("operational_hours_check_failed", error=str(e))

    system_prompt = f"""[IDENTITY]
    You are the official Customer Service AI Agent named {persona_name}.

    [CORE OBJECTIVE]
    Assist customers efficiently with product inquiries, sizing, order tracking, and store policies while maintaining a helpful and professional demeanor.

    [STRICT RULES & GUARDRAILS]
    1. DATA INTEGRITY: You MUST rely strictly on the provided context, knowledge base, or tool outputs. NEVER guess, assume, or hallucinate product details, prices, or stock availability.
    2. SERVICE BOUNDARY: If a user asks about topics unrelated to fashion, your store's products, or their specific orders (e.g., coding, politics, general trivia), you MUST politely decline and steer the conversation back to the store.
    3. CONTEXTUAL MEMORY: You may respond to casual greetings (e.g., "halo") and remember the user's name if provided in the chat history, but always pivot to offering store assistance.
    4. HONESTY: If a tool fails or information is missing, admit you do not know and offer to connect them to a human agent.
    5. CONVERSATION ID: {conversation_id} - IMPORTANT: If you need to use any tools requiring a conversation_id (like escalate_to_human), use this ID exactly as is.
    6. CUSTOM RULES: {rules}
    7. OPERATIONAL STATUS: {op_hours_context}

    [TOOL USAGE STRATEGY]
    - Use `search_product` to find product names, categories, prices, sizes, and stock availability.
    - CROSS-SELLING (CRITICAL): You MUST use parallel tool calling. Whenever you decide to call `search_product` for the user's requested item, you MUST SIMULTANEOUSLY invoke a second `search_product` tool call for a complementary item (e.g., matching pants for a t-shirt) in the exact same turn. Do not wait for the first search to finish; execute both searches concurrently. Offer both items naturally to encourage cross-selling.
    - Use `check_discounts` to find active promotions, automatic discounts, or discount codes.
    - Use the available tools for product details, orders, and store info.
    - Do NOT call tools for basic greetings or store policy questions if the answer is already in your system knowledge.

    [TONE & FORMATTING]
    - Tone: {tone_of_voice}
    - Language: Always reply in Indonesian unless the user speaks another language.
    - Format: Keep answers concise (maximum 3-4 sentences). Avoid heavy markdown unless providing a list.
    
    [JSON OUTPUT FORMATTING]
    You MUST output valid JSON strictly matching the AgentResponseFormat schema:
    - messages: Your text response to the user.
    - has_product: Set to true ONLY if you are explicitly mentioning or recommending products in your response.
    - products: If has_product is true, you MUST provide a list of ALL products you mentioned, INCLUDING any complementary cross-sell products. If you recommend a main item and a cross-sell item, BOTH must be in this array. You MUST include `title`, `url` (or empty string), `image_url` (or empty string), and `price` (as a string) for each product based on the data returned by the tools. This is CRITICAL for the frontend UI to display product cards!
    """

    # Initialize controllers
    tools = await _build_tools( conversation_id, sys_config)

    llm_manager = LLMManager()

    try:
        llm = await llm_manager.get_static_llm(
            provider="google_genai",
            user_id=conversation_id,
            channel="shopify_chat",
            temperature=0.0,
            fallback_providers=["openrouter", "ollama"],
        )
    except Exception as e:
        logger.error("agentic_loop_failed_llm", error=str(e))
        await _handle_agent_error(db, conversation_id, e, "LLM Initialization", "System attempting to initialize the LLM for chat response.")
        final_response = {
            "messages": "Maaf, sistem kami sedang mengalami kendala teknis. Mohon tunggu beberapa saat atau hubungi tim support kami.",
            "has_product": False,
            "products": []
        }
    else:
        try:
            if not checkpointer:
                logger.warning("No checkpointer provided for LangGraph")

            agent = create_agent(
                model=llm,
                tools=tools,
                checkpointer=checkpointer,
                system_prompt=system_prompt,
                response_format=AgentResponseFormat,
                middleware=[
                    PIIMiddleware("email", strategy="redact", apply_to_input=True),
                    PIIMiddleware("credit_card", strategy="mask", apply_to_input=True)
                ]
            )

            config = {
                "configurable": {
                    "thread_id": conversation_id,
                    "user_id": conversation_id,
                }
            }
            input_message = {"messages": [("user", message)]}

            result = await agent.ainvoke(input_message, config)

            last_message = result["messages"][-1]
            raw_content = last_message.content

            # Extract token usage and cost
            total_tokens = 0
            cost = 0.0
            logger.info(f"DEBUG_TOKENS: type(last_message)={type(last_message)}")
            logger.info(f"DEBUG_TOKENS: usage_metadata={getattr(last_message, 'usage_metadata', None)}")
            logger.info(f"DEBUG_TOKENS: response_metadata={getattr(last_message, 'response_metadata', None)}")
            
            if hasattr(last_message, "usage_metadata") and last_message.usage_metadata:
                total_tokens = last_message.usage_metadata.get("total_tokens", 0)
            elif hasattr(last_message, "response_metadata") and "token_usage" in last_message.response_metadata:
                total_tokens = last_message.response_metadata["token_usage"].get("total_tokens", 0)
                
            if hasattr(last_message, "response_metadata"):
                # Try to extract cost from typical OpenRouter locations
                resp_meta = last_message.response_metadata
                
                # Sometimes cost is directly in the response metadata root
                if "cost" in resp_meta:
                    cost = float(resp_meta["cost"])
                elif "usage" in resp_meta and isinstance(resp_meta["usage"], dict):
                    # Check natively inside usage
                    cost = float(resp_meta["usage"].get("cost", 0.0))
                elif "token_usage" in resp_meta and "cost" in resp_meta["token_usage"]:
                    cost = float(resp_meta["token_usage"].get("cost", 0.0))
                    
                # OpenRouter sometimes places it inside extra_info
                if cost == 0.0 and "extra_info" in resp_meta and isinstance(resp_meta["extra_info"], dict):
                    cost = float(resp_meta["extra_info"].get("cost", 0.0))
                
            logger.info(f"DEBUG_TOKENS: total_tokens = {total_tokens}, cost = {cost}")

            # Extract structured response from tool calls if available
            final_response = None
            
            # Traverse messages backwards to find the AIMessage that called AgentResponseFormat
            for msg in reversed(result["messages"]):
                if msg.__class__.__name__ == "AIMessage" and hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc.get("name") == "AgentResponseFormat" or tc.get("name") == "structured_response":
                            final_response = tc.get("args")
                            break
                if final_response:
                    break

            if not final_response:
                if isinstance(raw_content, dict):
                    final_response = raw_content
                    final_response_text = str(raw_content)
                else:
                    if isinstance(raw_content, list):
                        final_response_text = "".join(
                            part.get("text", "")
                            for part in raw_content
                            if isinstance(part, dict)
                        )
                    else:
                        final_response_text = str(raw_content)
    
                    import json
                    import re
                    import ast
                    try:
                        clean_text = final_response_text.strip()
                        if clean_text.startswith("```json"):
                            clean_text = clean_text[7:]
                        if clean_text.startswith("```"):
                            clean_text = clean_text[3:]
                        if clean_text.endswith("```"):
                            clean_text = clean_text[:-3]
                        clean_text = clean_text.strip()
                        
                        # Try to extract everything from first { to last }
                        match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                        if match:
                            clean_text = match.group(0)
                            
                        try:
                            final_response = json.loads(clean_text)
                        except Exception:
                            # Fallback for single-quoted Python dicts
                            final_response = ast.literal_eval(clean_text)
                        
                        if not isinstance(final_response, dict):
                            raise ValueError("Parsed output is not a dictionary")
                            
                    except Exception as e:
                        logger.error("failed_to_parse_agent_json", error=str(e), text=final_response_text)
                        final_response = {
                            "messages": final_response_text,
                            "has_product": False,
                            "products": []
                        }

            # Final safety check on the dict format
            if "messages" not in final_response:
                final_response["messages"] = "Maaf, saya tidak dapat memformat pesan."
            if "has_product" not in final_response:
                final_response["has_product"] = False
            if "products" not in final_response:
                final_response["products"] = []

        except Exception as e:
            logger.exception("agentic_loop_execution_error")
            await _handle_agent_error(db, conversation_id, e, "Agent Loop Execution", "AI Agent attempting to orchestrate tools and formulate a response.")
            final_response = {
                "messages": "Maaf, sistem kami sedang mengalami kendala teknis. Mohon tunggu beberapa saat atau hubungi tim support kami.",
                "has_product": False,
                "products": []
            }
            total_tokens = 0
            cost = 0.0

        # Save AI message to DB
        try:
            import json
            from app.models.conversation import Conversation
            
            new_message = Message(
                conversation_id=uuid.UUID(conversation_id),
                sender_type="ai",
                content=final_response.get("messages", str(final_response)),
                token_usage=total_tokens,
                cost=cost,
            )
            db.add(new_message)
            
            # Update Conversation totals
            conv = await db.get(Conversation, uuid.UUID(conversation_id))
            if conv:
                conv.total_token += total_tokens
                conv.total_cost += cost
                
            await db.commit()
        except Exception as e:
            logger.exception("db_save_ai_message_failed", error=str(e))

        # Send response to customer
        payload = {
            "type": "message",
            "sender": "ai",
            "text": final_response.get("messages", ""),
            "messages": final_response.get("messages", ""),
            "has_product": final_response.get("has_product", False),
            "products": final_response.get("products", [])
        }
        
        await manager.send_to_customer(
            conversation_id,
            payload,
        )

        # Broadcast response to dashboard
        dashboard_payload = payload.copy()
        dashboard_payload["conversation_id"] = conversation_id
        await manager.broadcast_to_dashboard(dashboard_payload)

        logger.info("agentic_loop_completed", conversation_id=conversation_id)
    return final_response

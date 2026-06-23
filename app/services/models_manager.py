"""
LLM Manager Service for dynamic initialization and fallback of chat models.
"""

import logging
from typing import Optional, List, Dict, Any
from langchain.chat_models import init_chat_model
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from app.core.config import get_settings

logger = logging.getLogger(__name__)

import time

class LLMManager:
    """Manages the lifecycle and fallback mechanism of Large Language Models."""
    
    # Class-level state to remember rate-limited providers across requests
    _rate_limited_providers: Dict[str, float] = {}
    _active_llm_provider: Optional[str] = None
    _active_embed_provider: Optional[str] = None
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.priority_list = self.settings.llm_priority_list
        self.embed_priority_list = self.settings.embed_priority_list
        self.__llm_maps: Dict[str, Dict[str, Any]] = {
            "ollama": {
                "base_url": self.settings.OLLAMA_BASE_URL,
                "model": self.settings.OLLAMA_CHAT_MODEL,
                "langchain_name": lambda m: f"ollama:{m}"
            },
            "openrouter": {
                "api_key": self.settings.OPENROUTER_API_KEY,
                "model": self.settings.OPENROUTER_CHAT_MODEL,
                "langchain_name": lambda m: m
            },
            "google_genai": {
                "api_key": self.settings.GOOGLEGENAI_API_KEY,
                "model": self.settings.GOOGLEGENAI_CHAT_MODEL,
                "langchain_name": lambda m: f"google_genai:{m}"
            },
            "groq": {
                "api_key": self.settings.GROQ_API_KEY,
                "model": self.settings.GROQ_CHAT_MODEL,
                "langchain_name": lambda m: f"groq:{m}"
            }
        }
        
        self.__embed_maps: Dict[str, Dict[str, Any]] = {
            "openai": {
                "api_key": self.settings.OPENAI_API_KEY,
                "model": self.settings.OPENAI_EMBEDDING_MODEL,
            },
            "google_genai": {
                "api_key": self.settings.GOOGLEGENAI_API_KEY,
                "model": self.settings.GOOGLEGENAI_EMBEDDING_MODEL,
            },
            "ollama": {
                "base_url": self.settings.OLLAMA_BASE_URL,
                "model": self.settings.OLLAMA_EMBEDDING_MODEL,
            }
        }

    def _build_callbacks(
        self, 
        user_id: str = "system", 
        channel: str = "internal",
        extra_callbacks: Optional[List[AsyncCallbackHandler]] = None
    ) -> List[AsyncCallbackHandler]:
        """Build callback list including cost tracking."""
        callbacks: List[AsyncCallbackHandler] = []
        try:
            from app.services.llms.callbacks import GlobalCostHandler
            callbacks.append(GlobalCostHandler(user_id=user_id, channel=channel))
        except ImportError:
            logger.warning("GlobalCostHandler could not be imported. Cost tracking disabled.")
            
        if extra_callbacks:
            callbacks.extend(extra_callbacks)
        return callbacks
    
    def _init_provider_model(
        self, 
        provider: str, 
        provider_map: Dict[str, Any], 
        callbacks: List[AsyncCallbackHandler], 
        **kwargs: Any
    ) -> BaseChatModel:
        """Inisialisasi base model berdasarkan provider map."""
        model_name = provider_map["model"]
        if not model_name:
             raise ValueError(f"Model name for provider '{provider}' is not set.")
             
        llm_id = provider_map["langchain_name"](model_name)
        
        if provider.lower() == "ollama":
            return init_chat_model(
                llm_id,
                base_url=provider_map["base_url"],
                callbacks=callbacks,
                timeout=self.settings.LLM_TIMEOUT_SECONDS,
                max_retries=3,
                **kwargs
            )
        elif provider.lower() == "openrouter":
            from langchain_openrouter import ChatOpenRouter
            api_key = provider_map.get("api_key")
            if not api_key:
                raise ValueError(f"API key for provider '{provider}' is not set.")
            return ChatOpenRouter(
                api_key=api_key,
                model=model_name,
                callbacks=callbacks,
                request_timeout=self.settings.LLM_TIMEOUT_SECONDS,
                max_retries=3,
                **kwargs
            )
        elif provider.lower() == "google_genai":
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = provider_map.get("api_key")
            if not api_key:
                raise ValueError(f"API key for provider '{provider}' is not set.")
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                callbacks=callbacks,
                timeout=self.settings.LLM_TIMEOUT_SECONDS,
                max_retries=3,
                **kwargs
            )
        else:
            api_key = provider_map.get("api_key")
            if not api_key:
                raise ValueError(f"API key for provider '{provider}' is not set.")
            
            return init_chat_model(
                llm_id,
                api_key=api_key,
                callbacks=callbacks,
                timeout=self.settings.LLM_TIMEOUT_SECONDS,
                max_retries=3,
                **kwargs
            )

    async def get_static_llm(
        self, 
        provider: str = "openai", 
        chat_model: Optional[str] = None, 
        user_id: str = "system",
        channel: str = "internal",
        callbacks: Optional[List[AsyncCallbackHandler]] = None,
        check_health: bool = False,
        fallback_providers: Optional[List[str]] = None,
        **kwargs: Any
    ) -> BaseChatModel:
        
        provider_map = self.__llm_maps.get(provider.lower())
        if not provider_map:
            logger.error(f"Provider: {provider} not configured.")
            raise RuntimeError(f"Static provider '{provider}' not found")
        
        if chat_model:
            provider_map = provider_map.copy()
            provider_map["model"] = chat_model
            
        all_callbacks = self._build_callbacks(user_id, channel, callbacks)
        
        try:
            llm = self._init_provider_model(provider, provider_map, all_callbacks, **kwargs)
            
            # Setup Fallbacks
            if fallback_providers:
                fallback_models = []
                for fb_prov in fallback_providers:
                    fb_prov_map = self.__llm_maps.get(fb_prov.lower())
                    if fb_prov_map:
                        try:
                            fb_llm = self._init_provider_model(fb_prov.lower(), fb_prov_map, all_callbacks, **kwargs)
                            fallback_models.append(fb_llm)
                        except Exception as fb_e:
                            logger.warning(f"Failed to init fallback {fb_prov}: {fb_e}")
                if fallback_models:
                    llm = llm.with_fallbacks(fallback_models)
            
            if check_health:
                is_health = await llm.ainvoke("Reply with the word OK only.")
                logger.info(f"✔ LLM {provider} active → {is_health.content}")
                
            return llm
            
        except Exception as e:
            logger.error(f"❌ {provider} initialization failed → {e}")
            raise RuntimeError(f"Static provider '{provider}' init failed → {e}")
        
    async def get_auto_llm(
        self, 
        user_id: str = "system",
        channel: str = "internal",
        callbacks: Optional[List[AsyncCallbackHandler]] = None,
        check_health: bool = False,
        **kwargs: Any
    ) -> BaseChatModel:
        
        all_callbacks = self._build_callbacks(user_id, channel, callbacks)
        current_time = time.time()
        
        class FallbackErrorHandler(AsyncCallbackHandler):
            def __init__(self, provider_name: str, manager_cls):
                self.provider_name = provider_name
                self.manager_cls = manager_cls
                
            async def on_llm_error(self, error: BaseException, **kwargs: Any) -> Any:
                logger.warning(f"⚠️ {self.provider_name} failed during execution. Adding to cooldown. Reason: {error}")
                self.manager_cls._rate_limited_providers[self.provider_name] = time.time() + 60
                if self.manager_cls._active_llm_provider == self.provider_name:
                    self.manager_cls._active_llm_provider = None

        providers_to_try = self.priority_list.copy()
        if self.__class__._active_llm_provider in providers_to_try:
            providers_to_try.remove(self.__class__._active_llm_provider)
            providers_to_try.insert(0, self.__class__._active_llm_provider)

        available_llms = []
        
        for provider in providers_to_try:
            provider = provider.lower()
            
            # Check cooldown
            expiry_time = self.__class__._rate_limited_providers.get(provider, 0)
            if current_time < expiry_time:
                logger.info(f"⏭️ Skipping {provider} as it is currently rate-limited or unavailable.")
                continue
                
            provider_map = self.__llm_maps.get(provider)
            if not provider_map:
                logger.warning(f"Provider {provider} is in priority list but not configured.")
                continue

            try:
                # Inject the error handler specific to this provider
                provider_callbacks = all_callbacks + [FallbackErrorHandler(provider, self.__class__)]
                llm = self._init_provider_model(provider, provider_map, provider_callbacks, **kwargs)

                if check_health:
                    is_health = await llm.ainvoke("Reply with the word OK only.")
                    logger.info(f"✔ Auto-LLM {provider} passed health check → {is_health.content}")

                available_llms.append((provider, llm))
            
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "rate limit" in error_str or "quota" in error_str or "401" in error_str or "unauthorized" in error_str or "incorrect api key" in error_str:
                    logger.warning(f"⚠️ {provider} hit rate limit or auth error during init. Cooldown for 60s. Reason: {e}")
                    self.__class__._rate_limited_providers[provider] = current_time + 60
                else:
                    logger.warning(f"⚠️ {provider} failed init, falling back to next provider. Reason: {e}")
                continue

        if not available_llms:
            logger.error("❌ All LLM providers in priority list failed.")
            raise RuntimeError("No available LLM provider passed health check or initialization.")

        # Set active cache
        primary_provider, primary_llm = available_llms[0]
        self.__class__._active_llm_provider = primary_provider
        
        # Attach native fallbacks if there are multiple providers
        if len(available_llms) > 1:
            fallback_models = [llm for _, llm in available_llms[1:]]
            return primary_llm.with_fallbacks(fallback_models)
            
        return primary_llm

    def _init_provider_embed_model(
        self, 
        provider: str, 
        provider_map: Dict[str, Any],
        **kwargs: Any
    ) -> Embeddings:
        """Inisialisasi embedding model berdasarkan provider map."""
        model_name = provider_map["model"]
        if not model_name:
             raise ValueError(f"Embedding model name for provider '{provider}' is not set.")
             
        if provider.lower() == "openai":
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(
                model=model_name,
                api_key=provider_map["api_key"],
                **kwargs
            )
        elif provider.lower() == "google_genai":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            return GoogleGenerativeAIEmbeddings(
                model=model_name,
                google_api_key=provider_map["api_key"],
                output_dimensionality=1536,
                **kwargs
            )
        elif provider.lower() == "ollama":
            from langchain_ollama import OllamaEmbeddings
            return OllamaEmbeddings(
                model=model_name,
                base_url=provider_map["base_url"],
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported embedding provider '{provider}'")

    async def get_static_embed_model(
        self, 
        provider: str = "openai", 
        embed_model: Optional[str] = None,
        check_health: bool = False,
        **kwargs: Any
    ) -> Embeddings:
        
        provider_map = self.__embed_maps.get(provider.lower())
        if not provider_map:
            logger.error(f"Embed Provider: {provider} not configured.")
            raise RuntimeError(f"Static embed provider '{provider}' not found")
        
        if embed_model:
            provider_map = provider_map.copy()
            provider_map["model"] = embed_model
            
        try:
            embeddings = self._init_provider_embed_model(provider, provider_map, **kwargs)
            
            if check_health:
                await embeddings.aembed_query("test")
                logger.info(f"✔ Embed {provider} active")
                
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ {provider} embed init failed → {e}")
            raise RuntimeError(f"Static embed provider '{provider}' init failed → {e}")

    async def get_auto_embed_model(
        self, 
        check_health: bool = False,
        **kwargs: Any
    ) -> Embeddings:
        
        current_time = time.time()
        
        providers_to_try = self.embed_priority_list.copy()
        if self.__class__._active_embed_provider in providers_to_try:
            providers_to_try.remove(self.__class__._active_embed_provider)
            providers_to_try.insert(0, self.__class__._active_embed_provider)
        
        for provider in providers_to_try:
            provider = provider.lower()
            
            # Check cooldown
            expiry_time = self.__class__._rate_limited_providers.get(provider, 0)
            if current_time < expiry_time:
                logger.info(f"⏭️ Skipping embed {provider} as it is currently rate-limited.")
                continue
                
            provider_map = self.__embed_maps.get(provider)
            if not provider_map:
                logger.warning(f"Embed Provider {provider} is in priority list but not configured.")
                continue

            try:
                embeddings = self._init_provider_embed_model(provider, provider_map, **kwargs)

                if check_health:
                    await embeddings.aembed_query("test")
                    logger.info(f"✔ Auto-Embed {provider} passed health check")

                self.__class__._active_embed_provider = provider
                return embeddings
            
            except Exception as e:
                error_str = str(e).lower()
                logger.warning(f"⚠️ Embed {provider} failed init/health. Cooldown for 60s. Reason: {e}")
                self.__class__._rate_limited_providers[provider] = current_time + 60
                if self.__class__._active_embed_provider == provider:
                    self.__class__._active_embed_provider = None
                continue

        logger.error("❌ All Embed providers in priority list failed.")
        raise RuntimeError("No available Embed provider passed health check or initialization.")
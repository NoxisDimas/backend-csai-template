import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.models_manager import LLMManager

async def test_fallbacks():
    manager = LLMManager()
    
    print("Testing groq (primary)")
    llm = await manager.get_static_llm(provider="groq", fallback_providers=["google_genai", "ollama"])
    
    print("LLM wrapper:", type(llm))
    
    try:
        res = await llm.ainvoke("Reply 'OK'")
        print("Success:", res.content)
    except Exception as e:
        print("Final Error:", type(e), e)

if __name__ == "__main__":
    asyncio.run(test_fallbacks())

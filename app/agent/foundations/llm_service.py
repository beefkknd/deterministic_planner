"""
LLM Service Foundation

Simple LLM service - just provides the LLM instance.
Chain creation is done in each node.
"""

from typing import Optional
from langchain_core.language_models import BaseChatModel

from app.agent.config import settings


class LLMService:
    """Simple LLM service - just holds the LLM instance."""

    _instance: Optional["LLMService"] = None

    def __init__(self, provider: str = None, model: str = None):
        provider = provider or settings.LLM_PROVIDER

        if provider == "local":
            from langchain_openai import ChatOpenAI
            model = model or settings.LOCAL_MODEL
            self.llm: BaseChatModel = ChatOpenAI(
                model=model,
                base_url=settings.LOCAL_BASE_URL,
                api_key=settings.LOCAL_API_KEY,
                temperature=0,
                max_tokens=4096,
            )
        else:
            from langchain_anthropic import ChatAnthropic
            model = model or settings.ANTHROPIC_MODEL
            self.llm = ChatAnthropic(
                model=model,
                temperature=0,
                max_tokens=4096,
            )

    @classmethod
    def get_instance(cls, provider: str = None, model: str = None) -> "LLMService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(provider, model)
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None


def get_llm() -> BaseChatModel:
    """Get the LLM instance."""
    return LLMService.get_instance().llm

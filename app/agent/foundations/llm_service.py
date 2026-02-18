"""
LLM Service Foundation

Provides LLM instance and chain for the agent.
Supports both local (LM Studio) and cloud (Anthropic) models.
"""

from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agent.config import settings as config


class LLMService:
    """Service for managing LLM instances and chains."""

    _instance: Optional["LLMService"] = None
    _llm: Optional[BaseChatModel] = None

    def __init__(self, provider: str = None, model: str = None):
        """
        Initialize LLM service.

        Args:
            provider: "local" or "anthropic" (default from config)
            model: Model name (default from config)
        """
        provider = provider or config.LLM_PROVIDER

        if provider == "local":
            model = model or config.LOCAL_MODEL
            self.model_name = model
            self._llm = ChatOpenAI(
                model=model,
                base_url=config.LOCAL_BASE_URL,
                api_key=config.LOCAL_API_KEY,
                temperature=0,
                max_tokens=4096,
            )
        else:
            model = model or config.ANTHROPIC_MODEL
            from langchain_anthropic import ChatAnthropic
            self.model_name = model
            self._llm = ChatAnthropic(
                model=model,
                temperature=0,
                max_tokens=4096,
            )

    @classmethod
    def get_instance(cls, provider: str = None, model: str = None) -> "LLMService":
        """Get singleton instance of LLMService."""
        if cls._instance is None:
            cls._instance = cls(provider, model)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (useful for testing with different models)."""
        cls._instance = None

    @property
    def llm(self) -> BaseChatModel:
        """Get the LLM instance."""
        return self._llm

    def create_chain(
        self,
        system_message: str,
        prompt_template: Optional[str] = None,
    ) -> ChatPromptTemplate:
        """
        Create a chat chain: prompt template | LLM | output parser.

        Args:
            system_message: System prompt/instructions
            prompt_template: Optional user prompt template with {variables}

        Returns:
            ChatPromptTemplate ready to be invoked with .chain()
        """
        if prompt_template:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                ("user", prompt_template)
            ])
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                MessagesPlaceholder(variable_name="messages", optional=True)
            ])

        return prompt | self._llm | StrOutputParser()

    def create_structured_chain(
        self,
        system_message: str,
        prompt_template: str,
        output_schema: type,
    ):
        """
        Create a chain that returns a Pydantic model instance.

        Uses LLM's with_structured_output() for reliable structured parsing.

        Args:
            system_message: System prompt/instructions
            prompt_template: User prompt template with {variables}
            output_schema: Pydantic BaseModel class for the output

        Returns:
            Chain: prompt | structured_llm
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", prompt_template)
        ])

        structured_llm = self._llm.with_structured_output(output_schema)
        return prompt | structured_llm


def get_llm() -> BaseChatModel:
    """Get the global LLM instance."""
    return LLMService.get_instance().llm


def get_llm_chain(system_message: str, prompt_template: Optional[str] = None):
    """Get a pre-configured LLM chain."""
    return LLMService.get_instance().create_chain(system_message, prompt_template)

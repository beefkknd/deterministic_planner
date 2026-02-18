"""
LLM Service Foundation

Simple LLM service with chain creation.
Matches pattern: PROMPT_TEMPLATE | llm | parser
"""

from typing import Optional, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agent.config import settings


class LLMService:
    """Simple LLM service with singleton pattern."""

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

    def create_chain(
        self,
        system_message: str,
        prompt_template: Optional[str] = None,
    ) -> ChatPromptTemplate:
        """
        Create a chain: prompt | llm | str_parser.

        Usage:
            chain = llm_service.create_chain(system_message, "{question}")
            result = chain.ainvoke({"question": "..."})
        """
        if prompt_template:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                ("human", prompt_template)
            ])
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                MessagesPlaceholder(variable_name="messages", optional=True)
            ])

        return prompt | self.llm | StrOutputParser()

    def create_structured_chain(
        self,
        system_message: str,
        prompt_template: str,
        output_schema: type,
    ) -> Any:
        """
        Create a chain with structured output (Pydantic).

        Usage:
            chain = llm_service.create_structured_chain(system, template, MyModel)
            result = chain.ainvoke({"var": "..."})
            # result is MyModel instance
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", prompt_template)
        ])

        structured_llm = self.llm.with_structured_output(output_schema)
        return prompt | structured_llm


# Convenience function
def get_llm_service() -> LLMService:
    """Get LLM service instance."""
    return LLMService.get_instance()

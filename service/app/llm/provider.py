"""Model-agnostic LLM provider abstraction.

Swapping from Gemini to Claude is a config change (LABSIGHT_LLM_PROVIDER),
no code changes needed. Both providers return a LangChain BaseChatModel
so the rest of the pipeline is provider-agnostic.
"""

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel

from app.config import Settings


class LLMProvider(ABC):
    """Interface that every LLM backend must implement."""

    @abstractmethod
    def get_chat_model(self) -> BaseChatModel:
        """Return a LangChain chat model ready for inference."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Human-readable model identifier for logging."""


def create_provider(settings: Settings) -> LLMProvider:
    """Factory: instantiate the configured LLM provider."""
    if settings.llm_provider == "vertex_ai":
        from app.llm.vertex_ai import VertexAIProvider

        return VertexAIProvider(settings)

    if settings.llm_provider == "openrouter":
        from app.llm.openrouter import OpenRouterProvider

        return OpenRouterProvider(settings)

    raise ValueError(
        f"Unknown LLM provider: {settings.llm_provider!r}. "
        "Must be 'vertex_ai' or 'openrouter'."
    )

"""OpenRouter LLM provider (Claude via OpenAI-compatible API).

OpenRouter exposes an OpenAI-compatible endpoint, so we use
langchain-openai's ChatOpenAI pointed at openrouter.ai. Steven has
existing OpenRouter credits for Claude access.
"""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import Settings
from app.llm.provider import LLMProvider

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.openrouter_model
        self._api_key = settings.openrouter_api_key

    def get_chat_model(self) -> BaseChatModel:
        return ChatOpenAI(
            model=self._model_name,
            openai_api_key=self._api_key,
            openai_api_base=_OPENROUTER_BASE_URL,
            streaming=True,
            temperature=0.1,
            max_tokens=2048,
        )

    def get_model_name(self) -> str:
        return f"openrouter/{self._model_name}"

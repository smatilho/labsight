"""Vertex AI (Gemini) LLM provider.

Uses langchain-google-vertexai for native GCP integration including
streaming support. Gemini 2.0 Flash is the default — fast, cheap, and
good enough for RAG synthesis.
"""

from langchain_core.language_models import BaseChatModel
from langchain_google_vertexai import ChatVertexAI

from app.config import Settings
from app.llm.provider import LLMProvider


class VertexAIProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.vertex_model
        self._project = settings.gcp_project
        self._location = settings.gcp_region

    def get_chat_model(self) -> BaseChatModel:
        return ChatVertexAI(
            model_name=self._model_name,
            project=self._project,
            location=self._location,
            streaming=True,
            temperature=0.1,
            max_output_tokens=2048,
        )

    def get_model_name(self) -> str:
        return f"vertex_ai/{self._model_name}"

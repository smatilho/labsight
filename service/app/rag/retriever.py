"""ChromaDB retriever with Cloud Run IAM authentication.

Wraps the ChromaDB HTTP client in a LangChain BaseRetriever so the rest
of the pipeline stays provider-agnostic. Embeds queries with the same
text-embedding-004 model used during ingestion — vectors MUST come from
the same model or cosine similarity is meaningless.

Authentication: ChromaDB runs on Cloud Run with IAM-only access. We
fetch a Google ID token and pass it as a Bearer token, same pattern as
the ingestion Cloud Function (ingestion/main.py:38-58).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.config import Settings

if TYPE_CHECKING:
    import chromadb

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-004"


class ChromaDBRetriever(BaseRetriever):
    """Retrieves documents from ChromaDB using Vertex AI query embeddings."""

    settings: Settings
    _embedding_model: Any = None

    model_config = {"arbitrary_types_allowed": True}

    def _get_client(self) -> chromadb.HttpClient:
        """Create an authenticated ChromaDB HTTP client with a fresh ID token.

        No caching — Google ID tokens expire after 1 hour and Cloud Run
        rejects stale ones. The ~10-20ms overhead of fetching a fresh token
        is negligible compared to embedding + LLM latency.
        """
        import chromadb
        import google.auth.transport.requests
        import google.oauth2.id_token

        url = self.settings.chromadb_url
        host = url.replace("https://", "").replace("http://", "").rstrip("/")
        ssl = url.startswith("https")

        auth_req = google.auth.transport.requests.Request()
        id_token = google.oauth2.id_token.fetch_id_token(auth_req, url)

        return chromadb.HttpClient(
            host=host,
            port=443 if ssl else 8000,
            ssl=ssl,
            headers={"Authorization": f"Bearer {id_token}"},
        )

    def _get_embedding_model(self) -> Any:
        """Lazy-init the Vertex AI embedding model."""
        if self._embedding_model is not None:
            return self._embedding_model

        import vertexai
        from vertexai.language_models import TextEmbeddingModel

        vertexai.init(
            project=self.settings.gcp_project,
            location=self.settings.gcp_region,
        )
        self._embedding_model = TextEmbeddingModel.from_pretrained(
            _EMBEDDING_MODEL
        )
        return self._embedding_model

    def _embed_query(self, query: str) -> list[float]:
        """Embed a single query string with text-embedding-004."""
        model = self._get_embedding_model()
        embeddings = model.get_embeddings([query])
        return embeddings[0].values

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        """Embed the query, search ChromaDB, return ranked Documents."""
        query_vector = self._embed_query(query)

        client = self._get_client()
        collection = client.get_collection(
            name=self.settings.chromadb_collection,
        )

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=self.settings.retrieval_top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents: list[Document] = []
        for doc_text, metadata, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB returns L2 distance by default; convert to a
            # 0-1 similarity score (lower distance = higher similarity).
            similarity = 1.0 / (1.0 + distance)

            doc_metadata = dict(metadata) if metadata else {}
            doc_metadata["similarity_score"] = round(similarity, 4)
            doc_metadata["distance"] = round(distance, 4)

            documents.append(
                Document(page_content=doc_text, metadata=doc_metadata)
            )

        logger.info(
            "Retrieved %d documents for query (top score: %.4f)",
            len(documents),
            documents[0].metadata["similarity_score"] if documents else 0,
        )
        return documents

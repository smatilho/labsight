"""Tests for ChromaDB retriever.

chromadb is stubbed in conftest.py (sys.modules) to avoid the Pydantic V1
crash on Python 3.14. All external deps (GCP auth, Vertex AI) are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.rag.retriever import ChromaDBRetriever


@pytest.fixture
def retriever(settings: Settings) -> ChromaDBRetriever:
    return ChromaDBRetriever(settings=settings)


@pytest.fixture
def mock_chromadb_collection() -> MagicMock:
    return MagicMock()


@pytest.fixture(autouse=True)
def _patch_externals(mock_chromadb_collection: MagicMock):
    """Patch GCP auth and Vertex AI for all retriever tests."""
    import chromadb  # this is our stub from conftest

    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_chromadb_collection
    chromadb.HttpClient = MagicMock(return_value=mock_client)

    with (
        patch(
            "google.oauth2.id_token.fetch_id_token",
            return_value="fake-id-token",
        ),
        patch("vertexai.init"),
        patch("vertexai.language_models.TextEmbeddingModel") as mock_embed_cls,
    ):
        mock_embedding = MagicMock()
        mock_embedding.values = [0.1] * 768
        mock_model = MagicMock()
        mock_model.get_embeddings.return_value = [mock_embedding]
        mock_embed_cls.from_pretrained.return_value = mock_model
        yield


class TestChromaDBRetriever:
    def test_retrieve_returns_documents(
        self,
        retriever: ChromaDBRetriever,
        mock_chromadb_collection: MagicMock,
    ) -> None:
        mock_chromadb_collection.query.return_value = {
            "documents": [["chunk one", "chunk two"]],
            "metadatas": [[{"source": "doc.md"}, {"source": "doc.md"}]],
            "distances": [[0.5, 1.2]],
        }

        docs = retriever.invoke("what is AdGuard?")

        assert len(docs) == 2
        assert docs[0].page_content == "chunk one"
        assert docs[0].metadata["source"] == "doc.md"
        assert "similarity_score" in docs[0].metadata
        # Closer distance should yield higher similarity
        assert docs[0].metadata["similarity_score"] > docs[1].metadata["similarity_score"]

    def test_retrieve_empty_results(
        self,
        retriever: ChromaDBRetriever,
        mock_chromadb_collection: MagicMock,
    ) -> None:
        mock_chromadb_collection.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        docs = retriever.invoke("nonexistent topic")
        assert docs == []

    def test_similarity_score_calculation(
        self,
        retriever: ChromaDBRetriever,
        mock_chromadb_collection: MagicMock,
    ) -> None:
        """Distance 0 -> similarity 1.0, large distance -> near 0."""
        mock_chromadb_collection.query.return_value = {
            "documents": [["perfect match", "distant match"]],
            "metadatas": [[{}, {}]],
            "distances": [[0.0, 100.0]],
        }

        docs = retriever.invoke("test")
        assert docs[0].metadata["similarity_score"] == 1.0
        assert docs[1].metadata["similarity_score"] < 0.02

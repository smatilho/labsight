"""Tests for the Vertex AI embedder (mocked — no real API calls)."""

from unittest.mock import MagicMock, patch

from embedder import VertexEmbedder, _MAX_BATCH_SIZE


class TestVertexEmbedder:
    def _make_mock_embedding(self, dim: int = 768) -> MagicMock:
        """Create a mock embedding object with a .values list."""
        mock = MagicMock()
        mock.values = [0.1] * dim
        return mock

    @patch("embedder.TextEmbeddingModel")
    @patch("embedder.vertexai")
    def test_embed_returns_vectors(self, mock_vertexai, mock_model_cls):
        mock_model = MagicMock()
        mock_model.get_embeddings.return_value = [
            self._make_mock_embedding(),
            self._make_mock_embedding(),
        ]
        mock_model_cls.from_pretrained.return_value = mock_model

        embedder = VertexEmbedder(project="test-project", location="us-east1")
        result = embedder.embed(["hello", "world"])

        assert result.text_count == 2
        assert len(result.vectors) == 2
        assert result.dimension == 768
        assert result.elapsed_ms > 0

    @patch("embedder.TextEmbeddingModel")
    @patch("embedder.vertexai")
    def test_embed_batches_large_inputs(self, mock_vertexai, mock_model_cls):
        mock_model = MagicMock()
        mock_model.get_embeddings.side_effect = lambda batch: [
            self._make_mock_embedding() for _ in batch
        ]
        mock_model_cls.from_pretrained.return_value = mock_model

        embedder = VertexEmbedder(project="test-project", location="us-east1")
        texts = [f"text_{i}" for i in range(_MAX_BATCH_SIZE + 10)]
        result = embedder.embed(texts)

        # Should have made 2 API calls
        assert mock_model.get_embeddings.call_count == 2
        assert result.text_count == _MAX_BATCH_SIZE + 10
        assert len(result.vectors) == _MAX_BATCH_SIZE + 10

    @patch("embedder.TextEmbeddingModel")
    @patch("embedder.vertexai")
    def test_embed_empty_list(self, mock_vertexai, mock_model_cls):
        mock_model = MagicMock()
        mock_model.get_embeddings.return_value = []
        mock_model_cls.from_pretrained.return_value = mock_model

        embedder = VertexEmbedder(project="test-project", location="us-east1")
        result = embedder.embed([])

        assert result.text_count == 0
        assert result.vectors == []
        assert result.dimension == 0

    @patch("embedder.TextEmbeddingModel")
    @patch("embedder.vertexai")
    def test_embed_timing(self, mock_vertexai, mock_model_cls):
        mock_model = MagicMock()
        mock_model.get_embeddings.return_value = [self._make_mock_embedding()]
        mock_model_cls.from_pretrained.return_value = mock_model

        embedder = VertexEmbedder(project="test-project", location="us-east1")
        result = embedder.embed(["test"])

        assert isinstance(result.elapsed_ms, float)
        assert result.elapsed_ms >= 0

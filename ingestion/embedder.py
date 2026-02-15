"""Vertex AI embeddings wrapper for the ingestion pipeline.

Uses text-embedding-004 (768 dimensions) which is optimized for
retrieval tasks. Batches up to 250 texts per API call to stay within
Vertex AI limits and reduce round trips.
"""

import os
import time
from dataclasses import dataclass, field

import vertexai
from vertexai.language_models import TextEmbeddingModel


@dataclass
class EmbeddingResult:
    """Embeddings for a batch of texts."""

    vectors: list[list[float]]
    dimension: int
    elapsed_ms: float
    text_count: int


_MODEL_NAME = "text-embedding-004"
_MAX_BATCH_SIZE = 250


class VertexEmbedder:
    """Generates embeddings via Vertex AI text-embedding-004."""

    def __init__(
        self,
        project: str | None = None,
        location: str | None = None,
    ) -> None:
        self.project = project or os.environ.get("GCP_PROJECT")
        self.location = location or os.environ.get("GCP_LOCATION", "us-east1")
        vertexai.init(project=self.project, location=self.location)
        self._model = TextEmbeddingModel.from_pretrained(_MODEL_NAME)

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Embed a list of texts, batching as needed."""
        all_vectors: list[list[float]] = []
        start = time.monotonic()

        for i in range(0, len(texts), _MAX_BATCH_SIZE):
            batch = texts[i : i + _MAX_BATCH_SIZE]
            embeddings = self._model.get_embeddings(batch)
            all_vectors.extend([e.values for e in embeddings])

        elapsed_ms = (time.monotonic() - start) * 1000

        return EmbeddingResult(
            vectors=all_vectors,
            dimension=len(all_vectors[0]) if all_vectors else 0,
            elapsed_ms=elapsed_ms,
            text_count=len(texts),
        )

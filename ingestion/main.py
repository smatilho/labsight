"""Cloud Function entry point for document ingestion.

Triggered by GCS object creation in the uploads bucket. Pipeline:
  1. Download file from GCS
  2. Sanitize (strip private IPs, secrets)
  3. Chunk (file-type-aware strategy)
  4. Embed (Vertex AI text-embedding-004)
  5. Store vectors in ChromaDB
  6. Log result to BigQuery

Errors are logged to BigQuery with status='error' and re-raised so
Cloud Functions retries the invocation.
"""

import datetime
import logging
import os
import time

import chromadb
import functions_framework
import google.auth.transport.requests
import google.oauth2.id_token
from cloudevents.http import CloudEvent
from google.cloud import bigquery, storage

from chunker import DocumentChunker
from embedder import VertexEmbedder
from sanitizer import DocumentSanitizer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_COLLECTION_NAME = "labsight_docs"
_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB — homelab docs shouldn't be larger


def _get_chromadb_client() -> chromadb.HttpClient:
    """Create an authenticated ChromaDB HTTP client.

    ChromaDB 1.x removed built-in token auth; authentication is handled
    entirely by Cloud Run IAM. The ingestion SA has roles/run.invoker on
    the ChromaDB service, so we just need a Google ID token in the
    Authorization header to prove our identity.
    """
    url = os.environ["CHROMADB_URL"]
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


def _log_to_bigquery(
    bq_client: bigquery.Client,
    table_id: str,
    *,
    file_name: str,
    file_type: str,
    file_size_bytes: int,
    chunk_count: int = 0,
    chunks_sanitized: int = 0,
    sanitization_actions: list[str] | None = None,
    embedding_time_ms: float = 0,
    total_time_ms: float = 0,
    status: str = "success",
    error_message: str | None = None,
) -> None:
    """Insert a row into the ingestion_log BigQuery table."""
    row = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "file_name": file_name,
        "file_type": file_type,
        "file_size_bytes": file_size_bytes,
        "chunk_count": chunk_count,
        "chunks_sanitized": chunks_sanitized,
        "sanitization_actions": sanitization_actions or [],
        "embedding_time_ms": embedding_time_ms,
        "total_time_ms": total_time_ms,
        "status": status,
        "error_message": error_message,
    }
    errors = bq_client.insert_rows_json(table_id, [row])
    if errors:
        logger.error("BigQuery insert errors: %s", errors)


@functions_framework.cloud_event
def process_document(cloud_event: CloudEvent) -> None:
    """Process a newly uploaded document through the ingestion pipeline."""
    start_time = time.monotonic()

    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]
    file_type = file_name.rsplit(".", 1)[-1] if "." in file_name else "unknown"
    generation = data.get("generation", "0")

    logger.info("Processing %s from bucket %s", file_name, bucket_name)

    bq_client = bigquery.Client()
    table_id = os.environ["BIGQUERY_TABLE"]
    file_size_bytes = int(data.get("size", 0))

    # Reject oversized files before downloading — prevents OOM on large uploads
    if file_size_bytes > _MAX_FILE_SIZE_BYTES:
        logger.warning(
            "File %s exceeds size limit (%d bytes > %d), skipping",
            file_name, file_size_bytes, _MAX_FILE_SIZE_BYTES,
        )
        _log_to_bigquery(
            bq_client,
            table_id,
            file_name=file_name,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            status="error",
            error_message=f"File size {file_size_bytes} exceeds limit {_MAX_FILE_SIZE_BYTES}",
            total_time_ms=(time.monotonic() - start_time) * 1000,
        )
        return

    try:
        # 1. Download from GCS
        gcs_client = storage.Client()
        bucket = gcs_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        content = blob.download_as_text()
        file_size_bytes = blob.size or len(content.encode())
        logger.info("Downloaded %s (%d bytes)", file_name, file_size_bytes)

        # 2. Sanitize
        sanitizer = DocumentSanitizer()
        report = sanitizer.sanitize(content)
        logger.info(
            "Sanitization: %d redactions, actions=%s",
            report.redaction_count,
            report.actions,
        )

        # 3. Chunk
        chunker = DocumentChunker()
        chunks = chunker.chunk(report.sanitized_text, file_name)
        logger.info("Chunked into %d pieces", len(chunks))

        if not chunks:
            logger.warning("No chunks produced for %s, skipping", file_name)
            _log_to_bigquery(
                bq_client,
                table_id,
                file_name=file_name,
                file_type=file_type,
                file_size_bytes=file_size_bytes,
                status="success",
                total_time_ms=(time.monotonic() - start_time) * 1000,
            )
            return

        # 4. Embed
        embedder = VertexEmbedder()
        chunk_texts = [c.text for c in chunks]
        embedding_result = embedder.embed(chunk_texts)
        logger.info(
            "Embedded %d chunks in %.0fms (dim=%d)",
            embedding_result.text_count,
            embedding_result.elapsed_ms,
            embedding_result.dimension,
        )

        # 5. Store in ChromaDB
        chroma_client = _get_chromadb_client()
        collection = chroma_client.get_or_create_collection(name=_COLLECTION_NAME)

        ids = [f"{file_name}__gen{generation}__chunk_{i}" for i in range(len(chunks))]
        metadatas = [c.metadata for c in chunks]

        collection.upsert(
            ids=ids,
            documents=chunk_texts,
            embeddings=embedding_result.vectors,
            metadatas=metadatas,
        )
        logger.info("Stored %d vectors in ChromaDB collection '%s'", len(ids), _COLLECTION_NAME)

        # 6. Log success to BigQuery
        total_time_ms = (time.monotonic() - start_time) * 1000
        _log_to_bigquery(
            bq_client,
            table_id,
            file_name=file_name,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            chunk_count=len(chunks),
            chunks_sanitized=report.redaction_count,
            sanitization_actions=report.actions,
            embedding_time_ms=embedding_result.elapsed_ms,
            total_time_ms=total_time_ms,
            status="success",
        )
        logger.info("Complete: %s processed in %.0fms", file_name, total_time_ms)

    except Exception as exc:
        total_time_ms = (time.monotonic() - start_time) * 1000
        logger.exception("Failed to process %s", file_name)
        try:
            _log_to_bigquery(
                bq_client,
                table_id,
                file_name=file_name,
                file_type=file_type,
                file_size_bytes=file_size_bytes,
                status="error",
                error_message=str(exc)[:1024],
                total_time_ms=total_time_ms,
            )
        except Exception:
            logger.exception("Failed to log error to BigQuery")
        raise

"""Upload endpoints: file upload to GCS, ingestion status, recent uploads.

POST /api/upload         — Upload a file to GCS (triggers Cloud Function ingestion)
GET  /api/upload/status  — Check ingestion status for a specific file
GET  /api/upload/recent  — List the 20 most recent ingestion events
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import JSONResponse
from google.cloud import bigquery, storage
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Characters allowed in sanitized filenames
_SAFE_FILENAME_RE = re.compile(r"[^a-z0-9._-]")


class UploadResponse(BaseModel):
    file_name: str
    object_name: str
    bucket: str
    size_bytes: int
    status: str = "uploaded"


class UploadStatusResponse(BaseModel):
    file_name: str
    file_type: str | None = None
    status: str
    chunk_count: int | None = None
    chunks_sanitized: int | None = None
    total_time_ms: float | None = None
    error_message: str | None = None
    timestamp: str | None = None


class RecentUploadsResponse(BaseModel):
    files: list[UploadStatusResponse]


def _sanitize_filename(name: str) -> str:
    """Sanitize a filename: strip path components, lowercase, remove unsafe chars."""
    # Take only the final path component (prevents path traversal)
    name = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    name = name.lower().strip()
    name = _SAFE_FILENAME_RE.sub("_", name)
    # Collapse consecutive underscores
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "unnamed"


def _get_extension(filename: str) -> str:
    """Extract file extension (without dot), lowercased.

    For dotless filenames like ``Dockerfile``, returns the normalized
    basename so it can be matched against the allowlist.
    """
    # Strip path components first
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." in name:
        return name.rsplit(".", 1)[-1].lower()
    # Dotless filename — return the whole name lowered (e.g. "dockerfile")
    return name.lower()


@router.post("/api/upload", response_model=None)
async def upload_file(request: Request, file: UploadFile) -> UploadResponse | JSONResponse:
    settings = request.app.state.settings

    if not settings.gcs_uploads_bucket:
        return JSONResponse(
            status_code=503,
            content={"detail": "Upload endpoint is not configured."},
        )

    # Validate extension
    original_name = file.filename or "unnamed"
    ext = _get_extension(original_name)
    allowed = settings.get_allowed_extensions_set()
    if ext not in allowed:
        return JSONResponse(
            status_code=400,
            content={"detail": f"File type '.{ext}' is not supported."},
        )

    # Read file content and validate size
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        max_mb = settings.max_upload_size_bytes / (1024 * 1024)
        return JSONResponse(
            status_code=400,
            content={"detail": f"File exceeds maximum size of {max_mb:.0f} MB."},
        )

    # Generate unique object key
    safe_name = _sanitize_filename(original_name)
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:8]
    object_name = f"uploads/{now:%Y/%m/%d}/{short_uuid}-{safe_name}"

    # Upload to GCS
    try:
        client = storage.Client()
        bucket = client.bucket(settings.gcs_uploads_bucket)
        blob = bucket.blob(object_name)
        blob.metadata = {"x-goog-meta-original-name": original_name}
        blob.upload_from_string(content)
    except Exception:
        logger.exception("Failed to upload file to GCS")
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to upload file. Please try again."},
        )

    return UploadResponse(
        file_name=original_name,
        object_name=object_name,
        bucket=settings.gcs_uploads_bucket,
        size_bytes=len(content),
    )


@router.get("/api/upload/status", response_model=None)
async def upload_status(
    request: Request, file_name: str
) -> UploadStatusResponse | JSONResponse:
    settings = request.app.state.settings

    if not settings.bigquery_observability_dataset:
        return JSONResponse(
            status_code=503,
            content={"detail": "Upload status endpoint is not configured."},
        )

    try:
        client = bigquery.Client()
        query = f"""
            SELECT file_name, file_type, status, chunk_count, chunks_sanitized,
                   total_time_ms, error_message, timestamp
            FROM `{settings.gcp_project}.{settings.bigquery_observability_dataset}.ingestion_log`
            WHERE file_name = @file_name
            ORDER BY timestamp DESC
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("file_name", "STRING", file_name),
            ]
        )
        rows = list(client.query(query, job_config=job_config).result())

        if not rows:
            return UploadStatusResponse(file_name=file_name, status="processing")

        row = rows[0]
        return UploadStatusResponse(
            file_name=row.file_name,
            file_type=row.file_type,
            status=row.status or "success",
            chunk_count=row.chunk_count,
            chunks_sanitized=row.chunks_sanitized,
            total_time_ms=row.total_time_ms,
            error_message=row.error_message,
            timestamp=row.timestamp.isoformat() if row.timestamp else None,
        )

    except Exception:
        logger.exception("Failed to query ingestion status")
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to check upload status."},
        )


@router.get("/api/upload/recent", response_model=None)
async def upload_recent(request: Request) -> RecentUploadsResponse | JSONResponse:
    settings = request.app.state.settings

    if not settings.bigquery_observability_dataset:
        return JSONResponse(
            status_code=503,
            content={"detail": "Upload recent endpoint is not configured."},
        )

    try:
        client = bigquery.Client()
        query = f"""
            SELECT file_name, file_type, status, chunk_count, chunks_sanitized,
                   total_time_ms, error_message, timestamp
            FROM `{settings.gcp_project}.{settings.bigquery_observability_dataset}.ingestion_log`
            ORDER BY timestamp DESC
            LIMIT 20
        """
        rows = list(client.query(query).result())

        files = [
            UploadStatusResponse(
                file_name=row.file_name,
                file_type=row.file_type,
                status=row.status or "success",
                chunk_count=row.chunk_count,
                chunks_sanitized=row.chunks_sanitized,
                total_time_ms=row.total_time_ms,
                error_message=row.error_message,
                timestamp=row.timestamp.isoformat() if row.timestamp else None,
            )
            for row in rows
        ]

        return RecentUploadsResponse(files=files)

    except Exception:
        logger.exception("Failed to query recent ingestions")
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to retrieve recent uploads."},
        )

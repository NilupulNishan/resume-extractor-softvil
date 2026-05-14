"""
blob_service.py
---------------
Handles all Blob Storage operations for the pipeline.

Responsibilities:
  1. Upload a raw CV file (PDF or DOCX) to the 'raw-cvs' container
  2. Generate a time-limited SAS URL for that blob

The returned SAS URL becomes `blobUrl` — it flows into both
Cosmos DB (system of record) and AI Search (recruiter card display).
"""

import os
from datetime import datetime, timezone, timedelta

from azure.storage.blob import (
    BlobSasPermissions,
    generate_blob_sas,
)

from resume_pipeline.clients import (
    blob_service_client,
    RAW_CVS_CONTAINER,
)

# SAS token validity window — 1 hour for Phase 1
# Increase to 24h or use user-delegation SAS in production
SAS_EXPIRY_HOURS = 1


def upload_cv(file_bytes: bytes, candidate_id: str, file_extension: str) -> str:
    """
    Upload a CV file to the raw-cvs container.

    Args:
        file_bytes:     Raw bytes of the uploaded file (PDF or DOCX)
        candidate_id:   UUID4 string — used as the blob name for traceability
        file_extension: 'pdf' or 'docx' (without the dot)

    Returns:
        blob_name: The name of the blob in the container (e.g. 'abc-123.pdf')

    Raises:
        Exception if upload fails
    """
    blob_name = f"{candidate_id}.{file_extension.lower().strip('.')}"

    container_client = blob_service_client.get_container_client(RAW_CVS_CONTAINER)
    blob_client = container_client.get_blob_client(blob_name)

    content_type_map = {
        "pdf":  "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    content_type = content_type_map.get(file_extension.lower(), "application/octet-stream")

    blob_client.upload_blob(
        file_bytes,
        overwrite=True,
        content_settings=__build_content_settings(content_type),
    )

    return blob_name


def generate_sas_url(blob_name: str) -> str:
    """
    Generate a time-limited SAS URL for a blob in the raw-cvs container.

    The SAS URL grants read-only access for SAS_EXPIRY_HOURS.
    This URL is what gets stored as `blobUrl` — never store the raw connection string.

    Args:
        blob_name: The blob name returned by upload_cv()

    Returns:
        Full HTTPS SAS URL string

    Raises:
        Exception if SAS generation fails
    """
    account_name = blob_service_client.account_name
    account_key  = blob_service_client.credential.account_key

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=RAW_CVS_CONTAINER,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=SAS_EXPIRY_HOURS),
    )

    sas_url = (
        f"https://{account_name}.blob.core.windows.net"
        f"/{RAW_CVS_CONTAINER}/{blob_name}?{sas_token}"
    )

    return sas_url


def upload_cv_and_get_url(file_bytes: bytes, candidate_id: str, file_extension: str) -> dict:
    """
    Convenience function: upload + generate SAS URL in one call.
    This is what the pipeline.py orchestrator will call.

    Returns:
        {
            "blob_name": "abc-123.pdf",
            "sas_url":   "https://resumestorage26.blob.core.windows.net/raw-cvs/abc-123.pdf?sv=..."
        }
    """
    blob_name = upload_cv(file_bytes, candidate_id, file_extension)
    sas_url   = generate_sas_url(blob_name)

    return {
        "blob_name": blob_name,
        "sas_url":   sas_url,
    }


# ── Private helper ─────────────────────────────────────────────────────────────

def __build_content_settings(content_type: str):
    """Set correct MIME type on the blob so browsers handle downloads properly."""
    from azure.storage.blob import ContentSettings
    return ContentSettings(content_type=content_type)
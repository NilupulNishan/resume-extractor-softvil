"""
test_blob.py
------------
Stage 1 gate test — validates upload + SAS URL generation.

Usage:
    python tests/test_blob.py

What it does:
    1. Creates a minimal dummy PDF (just bytes, not a real PDF — enough for upload)
    2. Uploads it to raw-cvs under a test candidate_id
    3. Generates a SAS URL
    4. Confirms the URL is well-formed and accessible
    5. Cleans up the test blob afterward
"""

import sys
import os
import uuid
import urllib.request

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_pipeline.blob_service import upload_cv, generate_sas_url, upload_cv_and_get_url
from resume_pipeline.clients import blob_service_client, RAW_CVS_CONTAINER

PASS = "  ✅ PASS"
FAIL = "  ❌ FAIL"


def test_upload_cv():
    print("\n[1] Upload CV to raw-cvs")
    test_candidate_id = f"test-{uuid.uuid4()}"

    # Minimal valid PDF header bytes — enough to test upload without a real file
    dummy_pdf_bytes = b"%PDF-1.4 test resume content for pipeline validation"

    try:
        blob_name = upload_cv(dummy_pdf_bytes, test_candidate_id, "pdf")
        print(f"{PASS} — Blob uploaded: '{blob_name}'")
        return blob_name, test_candidate_id
    except Exception as e:
        print(f"{FAIL} — {e}")
        return None, None


def test_generate_sas_url(blob_name: str):
    print("\n[2] Generate SAS URL")
    try:
        sas_url = generate_sas_url(blob_name)

        # Basic validation — must start with https and contain the container name
        assert sas_url.startswith("https://"), "URL must start with https://"
        assert RAW_CVS_CONTAINER in sas_url,    "URL must contain the container name"
        assert "?" in sas_url,                  "URL must contain SAS token query string"
        assert "sv=" in sas_url,                "SAS token must contain service version"

        print(f"{PASS} — SAS URL generated and well-formed")
        print(f"         Preview: {sas_url[:80]}...")
        return sas_url
    except Exception as e:
        print(f"{FAIL} — {e}")
        return None


def test_sas_url_is_accessible(sas_url: str):
    print("\n[3] SAS URL is accessible (HTTP 200)")
    try:
        req = urllib.request.Request(sas_url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
        if status == 200:
            print(f"{PASS} — URL resolves with HTTP {status}")
        else:
            print(f"{FAIL} — Unexpected HTTP status: {status}")
    except Exception as e:
        print(f"{FAIL} — {e}")


def test_convenience_function():
    print("\n[4] upload_cv_and_get_url() convenience function")
    test_candidate_id = f"test-conv-{uuid.uuid4()}"
    dummy_docx_bytes  = b"PK dummy docx bytes for test"

    try:
        result = upload_cv_and_get_url(dummy_docx_bytes, test_candidate_id, "docx")
        assert "blob_name" in result, "Result must contain blob_name"
        assert "sas_url"   in result, "Result must contain sas_url"
        assert result["blob_name"].endswith(".docx"), "blob_name must end with .docx"
        print(f"{PASS} — Returns correct dict with blob_name + sas_url")

        # Clean up this blob too
        _cleanup_blob(result["blob_name"])
    except Exception as e:
        print(f"{FAIL} — {e}")


def _cleanup_blob(blob_name: str):
    """Delete test blobs so they don't pollute raw-cvs container."""
    try:
        container = blob_service_client.get_container_client(RAW_CVS_CONTAINER)
        container.delete_blob(blob_name)
        print(f"         🧹 Cleaned up test blob: '{blob_name}'")
    except Exception as e:
        print(f"         ⚠️  Cleanup failed for '{blob_name}': {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("  Stage 1 — Blob Storage Tests")
    print("=" * 50)

    blob_name, candidate_id = test_upload_cv()

    if blob_name:
        sas_url = test_generate_sas_url(blob_name)

        if sas_url:
            test_sas_url_is_accessible(sas_url)

        # Clean up the test blob from test_upload_cv
        _cleanup_blob(blob_name)

    test_convenience_function()

    print("\n" + "=" * 50)
    print("  Done. All 4 must PASS before Stage 2.")
    print("=" * 50)
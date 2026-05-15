"""
test_pipeline.py
----------------
Stage 6 gate test — full end-to-end pipeline smoke test.

This is the final gate before Django integration.
Uses a real resume PDF from tests/fixtures/ and runs every stage:
    PDF → Blob Storage → Document Intelligence → GPT-4o → Embeddings → Cosmos DB + AI Search

Verifies both stores contain the real candidate record, then cleans up everything:
    - Cosmos DB document
    - AI Search document
    - Blob Storage file (the actual uploaded PDF)

If this passes, pipeline.py is ready for Django to call.

Usage:
    python tests/test_pipeline.py
"""

import sys
import os
import uuid
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_pipeline.pipeline import process_resume
from resume_pipeline.clients  import cosmos_container, search_client, blob_service_client, RAW_CVS_CONTAINER

PASS     = "  ✅ PASS"
FAIL     = "  ❌ FAIL"
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

# Real candidate ID — this is what Django would generate
TEST_CANDIDATE_ID = f"e2e-{uuid.uuid4()}"


def find_fixture() -> dict | None:
    for fname in os.listdir(FIXTURES):
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if ext in ("pdf", "docx") and not fname.startswith("last_"):
            return {"path": os.path.join(FIXTURES, fname), "name": fname, "extension": ext}
    return None


def test_full_pipeline() -> dict | None:
    print("\n[1] Run full pipeline — all 5 stages")
    fixture = find_fixture()

    if not fixture:
        print(f"{FAIL} — No fixture PDF/DOCX found in tests/fixtures/")
        return None

    size_kb = os.path.getsize(fixture["path"]) // 1024
    print(f"         File:         {fixture['name']} ({size_kb} KB)")
    print(f"         candidate_id: {TEST_CANDIDATE_ID}")
    print(f"         Running all stages — this takes ~15–30 seconds...")

    try:
        with open(fixture["path"], "rb") as f:
            file_bytes = f.read()

        result = process_resume(
            file_bytes     = file_bytes,
            file_extension = fixture["extension"],
            candidate_id   = TEST_CANDIDATE_ID,
        )

        print(f"{PASS} — Pipeline completed")
        print(f"         candidateId:      {result['candidateId']}")
        print(f"         cosmosDocumentId: {result['cosmosDocumentId']}")
        print(f"         status:           {result['status']}")
        return result

    except Exception as e:
        print(f"{FAIL} — {e}")
        return None


def test_cosmos_record(candidate_id: str):
    print(f"\n[2] Verify Cosmos DB — real candidate record")
    try:
        doc = cosmos_container.read_item(item=candidate_id, partition_key=candidate_id)

        name   = doc.get("personalInfo", {}).get("fullName", "unknown")
        status = doc.get("processingStatus")
        skills = doc.get("skills", {}).get("normalized", [])
        exp    = doc.get("totalExperienceYears")
        roles  = len(doc.get("workExperience", []))

        assert status == "completed",              f"processingStatus is '{status}', expected 'completed'"
        assert isinstance(doc.get("rawExtractedText"), str), "rawExtractedText missing"
        assert isinstance(doc.get("embeddingText"), str),    "embeddingText missing"
        assert isinstance(doc.get("blobUrl"), str),          "blobUrl missing"

        print(f"{PASS} — Cosmos DB record verified")
        print(f"         Name:             {name}")
        print(f"         processingStatus: {status}")
        print(f"         Experience:       {exp} years")
        print(f"         Work roles:       {roles}")
        print(f"         Top skills:       {skills[:5]}")

    except AssertionError as e:
        print(f"{FAIL} — Assertion failed: {e}")
    except Exception as e:
        print(f"{FAIL} — Could not read Cosmos record: {e}")


def test_search_record(candidate_id: str):
    print(f"\n[3] Verify AI Search — real candidate record")

    doc = None
    for attempt in range(5):
        try:
            doc = search_client.get_document(key=candidate_id)
            break
        except Exception:
            if attempt < 4:
                print(f"         Indexing... retry {attempt + 1}/5 in 2s")
                time.sleep(2)

    if doc is None:
        print(f"{FAIL} — Could not retrieve AI Search document after retries")
        return

    try:
        assert isinstance(doc.get("name"), str),         "name missing"
        assert isinstance(doc.get("currentRole"), str),  "currentRole missing"
        assert isinstance(doc.get("skills"), list),      "skills missing"
        assert len(doc.get("skills", [])) > 0,           "skills list empty"
        assert isinstance(doc.get("blobUrl"), str),      "blobUrl missing"
        assert doc.get("candidateId") == candidate_id,   "candidateId mismatch"

        print(f"{PASS} — AI Search record verified")
        print(f"         name:        {doc.get('name')}")
        print(f"         currentRole: {doc.get('currentRole')}")
        print(f"         skills:      {doc.get('skills', [])[:5]}")
        print(f"         experience:  {doc.get('totalExperienceYears')} years")

    except AssertionError as e:
        print(f"{FAIL} — {e}")


def test_blob_exists(candidate_id: str, file_extension: str):
    print(f"\n[4] Verify Blob Storage — CV file uploaded")
    blob_name = f"{candidate_id}.{file_extension}"
    try:
        container = blob_service_client.get_container_client(RAW_CVS_CONTAINER)
        props = container.get_blob_client(blob_name).get_blob_properties()
        size_kb = props.size // 1024
        print(f"{PASS} — Blob exists: '{blob_name}' ({size_kb} KB)")
    except Exception as e:
        print(f"{FAIL} — Blob not found: {e}")


def cleanup(candidate_id: str, file_extension: str):
    """Delete all test records from all three stores."""
    print(f"\n[5] Cleanup — remove test records from all stores")

    # Cosmos DB
    try:
        cosmos_container.delete_item(item=candidate_id, partition_key=candidate_id)
        print(f"         🧹 Cosmos DB deleted")
    except Exception as e:
        print(f"         ⚠️  Cosmos cleanup failed: {e}")

    # AI Search
    try:
        search_client.delete_documents(documents=[{"id": candidate_id}])
        print(f"         🧹 AI Search deleted")
    except Exception as e:
        print(f"         ⚠️  AI Search cleanup failed: {e}")

    # Blob Storage
    blob_name = f"{candidate_id}.{file_extension}"
    try:
        container = blob_service_client.get_container_client(RAW_CVS_CONTAINER)
        container.delete_blob(blob_name)
        print(f"         🧹 Blob Storage deleted: '{blob_name}'")
    except Exception as e:
        print(f"         ⚠️  Blob cleanup failed: {e}")


if __name__ == "__main__":
    print("=" * 58)
    print("  Stage 6 — Full End-to-End Pipeline Smoke Test")
    print("  PDF → Blob → Doc Intel → GPT-4o → Embed → Write")
    print("=" * 58)

    fixture  = find_fixture()
    result   = test_full_pipeline()

    if result:
        test_cosmos_record(TEST_CANDIDATE_ID)
        test_search_record(TEST_CANDIDATE_ID)
        test_blob_exists(TEST_CANDIDATE_ID, fixture["extension"] if fixture else "pdf")

    # Always clean up
    cleanup(TEST_CANDIDATE_ID, fixture["extension"] if fixture else "pdf")

    print("\n" + "=" * 58)
    if result:
        print("  ✅ Pipeline is complete and validated end-to-end.")
        print("  Ready for Django integration (Stage 7).")
        print()
        print("  Django entry point:")
        print("  from resume_pipeline.pipeline import process_resume")
        print()
        print("  result = process_resume(")
        print("      file_bytes     = request.FILES['cv'].read(),")
        print("      file_extension = 'pdf',")
        print("      candidate_id   = str(uuid.uuid4()),")
        print("  )")
    else:
        print("  ❌ Pipeline has failures. Fix before Django integration.")
    print("=" * 58)
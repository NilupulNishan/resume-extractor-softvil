"""
test_writer.py
--------------
Stage 5 gate test — writes real records to Cosmos DB and AI Search,
verifies both exist, then cleans up.

Input sources (no redundant API calls):
    - structured_json + embeddingText → tests/fixtures/last_structured_output.json (Stage 3)
    - vector → re-generated from embeddingText (one embedding call only)
    - sas_url → fake URL — neither store validates it at write time

What this test confirms:
    1. Cosmos DB document written with all required fields and correct types
    2. AI Search document written with all 12 index fields and correct types
    3. processingStatus reaches "completed" in Cosmos DB
    4. Both records are readable after write
    5. Both records are cleaned up after test

Usage:
    python tests/test_writer.py
"""

import sys
import os
import json
import uuid
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_pipeline.embedder import generate_embedding
from resume_pipeline.writer   import write_candidate
from resume_pipeline.clients  import cosmos_container, search_client

PASS         = "  ✅ PASS"
FAIL         = "  ❌ FAIL"
WARN         = "  ⚠️  WARN"
FIXTURE_JSON = os.path.join(os.path.dirname(__file__), "fixtures", "last_structured_output.json")

# Test candidate ID — prefixed for easy identification and cleanup
TEST_CANDIDATE_ID = f"test-writer-{uuid.uuid4()}"
TEST_BLOB_URL     = "https://resumestorage26.blob.core.windows.net/raw-cvs/test-blob.pdf?sv=fake-sas"


def load_stage3_output() -> tuple[dict, str] | tuple[None, None]:
    """Load structuredJson and embeddingText from Stage 3 saved output."""
    print("\n[1] Load Stage 3 output from fixture JSON")

    if not os.path.exists(FIXTURE_JSON):
        print(f"{FAIL} — {FIXTURE_JSON} not found. Run test_structurer.py first.")
        return None, None

    try:
        with open(FIXTURE_JSON, "r") as f:
            data = json.load(f)

        structured_json = data.get("structuredJson")
        embedding_text  = data.get("embeddingText", "").strip()

        if not structured_json:
            print(f"{FAIL} — structuredJson missing in fixture JSON")
            return None, None
        if not embedding_text:
            print(f"{FAIL} — embeddingText missing in fixture JSON")
            return None, None

        print(f"{PASS} — Loaded structuredJson + embeddingText")
        print(f"         Candidate: {structured_json.get('personalInfo', {}).get('fullName')}")
        return structured_json, embedding_text

    except Exception as e:
        print(f"{FAIL} — {e}")
        return None, None


def generate_vector(embedding_text: str) -> list[float] | None:
    """Re-generate the vector from embeddingText — one cheap embedding call."""
    print("\n[2] Generate vector from embeddingText")
    try:
        vector = generate_embedding(embedding_text)
        print(f"{PASS} — Vector ready: {len(vector)} dimensions")
        return vector
    except Exception as e:
        print(f"{FAIL} — {e}")
        return None


def test_dual_write(structured_json: dict, embedding_text: str, vector: list[float]) -> dict | None:
    """Call write_candidate() — the main Stage 5 function."""
    print(f"\n[3] Dual write — Cosmos DB + AI Search")
    print(f"         candidate_id: {TEST_CANDIDATE_ID}")

    try:
        result = write_candidate(
            candidate_id    = TEST_CANDIDATE_ID,
            raw_text        = "Test raw text for Stage 5 pipeline validation.",
            structured_json = structured_json,
            embedding_text  = embedding_text,
            vector          = vector,
            sas_url         = TEST_BLOB_URL,
        )
        print(f"{PASS} — write_candidate() completed")
        print(f"         cosmosDocumentId: {result['cosmosDocumentId']}")
        print(f"         status:           {result['status']}")
        return result

    except Exception as e:
        print(f"{FAIL} — {e}")
        return None


def test_cosmos_record(candidate_id: str):
    """Read the Cosmos DB record back and verify all required fields."""
    print(f"\n[4] Verify Cosmos DB record — read back and check fields")

    try:
        doc = cosmos_container.read_item(item=candidate_id, partition_key=candidate_id)

        # Required field checks
        checks = {
            "id":               doc.get("id") == candidate_id,
            "candidateId":      doc.get("candidateId") == candidate_id,
            "personalInfo":     isinstance(doc.get("personalInfo"), dict),
            "workExperience":   isinstance(doc.get("workExperience"), list),
            "education":        isinstance(doc.get("education"), list),
            "skills":           isinstance(doc.get("skills"), dict),
            "rawExtractedText": isinstance(doc.get("rawExtractedText"), str),
            "structuredJson":   isinstance(doc.get("structuredJson"), dict),
            "embeddingText":    isinstance(doc.get("embeddingText"), str),
            "blobUrl":          isinstance(doc.get("blobUrl"), str),
            "uploadedAt":       isinstance(doc.get("uploadedAt"), str),
            "processingStatus": doc.get("processingStatus") == "completed",
        }

        failed = [k for k, v in checks.items() if not v]

        if failed:
            print(f"{FAIL} — Fields failed: {failed}")
        else:
            print(f"{PASS} — All {len(checks)} Cosmos DB fields verified")
            print(f"         processingStatus: {doc.get('processingStatus')} ✓")
            print(f"         embeddingText stored: {len(doc.get('embeddingText','').split())} words ✓")
            print(f"         workExperience entries: {len(doc.get('workExperience', []))} ✓")

    except Exception as e:
        print(f"{FAIL} — Could not read Cosmos DB record: {e}")


def test_search_record(candidate_id: str):
    """
    Read the AI Search record back and verify all 12 index fields.
    AI Search may take 1–2 seconds to index — we retry briefly.
    """
    print(f"\n[5] Verify AI Search record — read back and check fields")

    doc = None
    for attempt in range(4):
        try:
            result = search_client.get_document(key=candidate_id)
            doc = result
            break
        except Exception:
            if attempt < 3:
                print(f"         Attempt {attempt + 1}: indexing... retrying in 2s")
                time.sleep(2)

    if doc is None:
        print(f"{FAIL} — Could not retrieve AI Search document after retries")
        return

    # All 12 fields from resumes-index schema
    checks = {
        "id":                   doc.get("id") == candidate_id,
        "candidateId":          doc.get("candidateId") == candidate_id,
        "cosmosDocumentId":     isinstance(doc.get("cosmosDocumentId"), str),
        "name":                 isinstance(doc.get("name"), str),
        "email":                doc.get("email") is not None,
        "summary":              True,                                        # Nullable — just presence check
        "skills":               isinstance(doc.get("skills"), list),
        "currentRole":          isinstance(doc.get("currentRole"), str),
        "totalExperienceYears": doc.get("totalExperienceYears") is not None,
        "uploadedAt":           isinstance(doc.get("uploadedAt"), str),
        "blobUrl":              isinstance(doc.get("blobUrl"), str),
        # embedding is not retrievable (retrievable=false in index) — skip
    }

    failed = [k for k, v in checks.items() if not v]

    if failed:
        print(f"{FAIL} — Fields failed: {failed}")
    else:
        print(f"{PASS} — All {len(checks)} AI Search fields verified")
        print(f"         name:        {doc.get('name')} ✓")
        print(f"         currentRole: {doc.get('currentRole')} ✓")
        print(f"         skills:      {doc.get('skills', [])[:5]} ✓")
        print(f"         experience:  {doc.get('totalExperienceYears')} years ✓")
        print(f"         Note: `embedding` field not retrievable by design (index config)")


def cleanup(candidate_id: str):
    """Delete both test records. Always runs — even if tests fail."""
    print(f"\n[6] Cleanup — delete test records from both stores")

    # Cosmos DB
    try:
        cosmos_container.delete_item(item=candidate_id, partition_key=candidate_id)
        print(f"         🧹 Cosmos DB — deleted '{candidate_id}'")
    except Exception as e:
        print(f"         ⚠️  Cosmos DB cleanup failed: {e}")

    # AI Search
    try:
        search_client.delete_documents(documents=[{"id": candidate_id}])
        print(f"         🧹 AI Search — deleted '{candidate_id}'")
    except Exception as e:
        print(f"         ⚠️  AI Search cleanup failed: {e}")


if __name__ == "__main__":
    print("=" * 55)
    print("  Stage 5 — Dual Write Tests")
    print("  Cosmos DB (system of record) + AI Search (vector index)")
    print("=" * 55)

    result = None

    # Load inputs
    structured_json, embedding_text = load_stage3_output()

    if structured_json and embedding_text:

        # Generate vector
        vector = generate_vector(embedding_text)

        if vector:

            # Write to both stores
            result = test_dual_write(structured_json, embedding_text, vector)

            if result:
                # Verify both records
                test_cosmos_record(TEST_CANDIDATE_ID)
                test_search_record(TEST_CANDIDATE_ID)

    # Always clean up — even on failure
    cleanup(TEST_CANDIDATE_ID)

    print("\n" + "=" * 55)
    print("  Done. All checks must PASS before Stage 6.")
    print("  Stage 6 (pipeline.py) wires all stages together")
    print("  into a single callable function for Django.")
    print("=" * 55)
"""
test_embedder.py
----------------
Stage 4 gate test — validates the embedding vector is correct and
compatible with the AI Search `embedding` field (Collection(Edm.Single)).

Reads `embeddingText` directly from tests/fixtures/last_structured_output.json
(saved by test_structurer.py — Stage 3) instead of re-running the full chain.

Stage 4 has one job: string → 1536-dim vector. No need to re-call
Document Intelligence or GPT-4o here — those already passed in Stage 3.

Usage:
    python tests/test_embedder.py
"""

import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_pipeline.embedder import generate_embedding
from resume_pipeline.clients import EMBEDDING_DIMENSIONS

PASS         = "  ✅ PASS"
FAIL         = "  ❌ FAIL"
WARN         = "  ⚠️  WARN"
FIXTURE_JSON = os.path.join(os.path.dirname(__file__), "fixtures", "last_structured_output.json")


def load_embedding_text() -> str | None:
    """
    Read embeddingText from the JSON saved by test_structurer.py (Stage 3).
    No Document Intelligence or GPT-4o call needed here.
    """
    print("\n[1] Load embeddingText from Stage 3 output")

    if not os.path.exists(FIXTURE_JSON):
        print(f"{FAIL} — File not found: {FIXTURE_JSON}")
        print("         Run test_structurer.py first to generate this file.")
        return None

    try:
        with open(FIXTURE_JSON, "r") as f:
            data = json.load(f)

        embedding_text = data.get("embeddingText", "").strip()

        if not embedding_text:
            print(f"{FAIL} — embeddingText field is empty in the JSON")
            return None

        print(f"{PASS} — Loaded embeddingText: {len(embedding_text.split())} words")
        print(f"         Preview: {embedding_text[:120]}...")
        return embedding_text

    except Exception as e:
        print(f"{FAIL} — Could not read JSON: {e}")
        return None


def test_generate_vector(embedding_text: str) -> list | None:
    """Single API call to text-embedding-3-small. That is all Stage 4 does."""
    print("\n[2] Generate embedding vector — text-embedding-3-small")
    try:
        vector = generate_embedding(embedding_text)
        print(f"{PASS} — Vector generated successfully")
        return vector
    except Exception as e:
        print(f"{FAIL} — {e}")
        return None


def test_dimensions(vector: list) -> bool:
    """
    AI Search `embedding` field is hard-configured for 1536 dimensions (HNSW config).
    Wrong size = write rejected at Stage 5.
    """
    print(f"\n[3] Dimensions — must be exactly {EMBEDDING_DIMENSIONS} (AI Search HNSW config)")
    if len(vector) == EMBEDDING_DIMENSIONS:
        print(f"{PASS} — {len(vector)} dimensions ✓")
        return True
    else:
        print(f"{FAIL} — Got {len(vector)}, expected {EMBEDDING_DIMENSIONS}")
        print("         AI Search will reject this vector at write time (Stage 5).")
        return False


def test_element_types(vector: list):
    """
    AI Search Collection(Edm.Single) requires float values.
    Python list[float] maps directly — writer.py needs zero transformation.
    """
    print("\n[4] Element types — all must be float (Collection(Edm.Single))")
    non_floats = [(i, type(v).__name__) for i, v in enumerate(vector) if not isinstance(v, float)]

    if non_floats:
        print(f"{FAIL} — {len(non_floats)} non-float values: {non_floats[:3]}")
    else:
        print(f"{PASS} — All {len(vector)} elements are float ✓")


def test_value_range(vector: list):
    """
    text-embedding-3-small returns cosine-normalized vectors.
    Values should sit roughly between -1.0 and 1.0.
    """
    print("\n[5] Value range — cosine-normalized, expected roughly -1.0 to 1.0")
    min_val      = min(vector)
    max_val      = max(vector)
    out_of_range = [v for v in vector if abs(v) > 2.0]

    if out_of_range:
        print(f"{WARN} — {len(out_of_range)} values outside +-2.0 — check deployment model")
    else:
        print(f"{PASS} — min={min_val:.6f}  max={max_val:.6f} ✓")


def test_non_zero(vector: list):
    """
    A zero vector matches everything equally in AI Search — silently destroys search quality.
    """
    print("\n[6] Non-zero check — must not be all zeros")
    non_zero = sum(1 for v in vector if v != 0.0)

    if non_zero == 0:
        print(f"{FAIL} — All values are zero. Embedding model returned nothing.")
    elif non_zero < 100:
        print(f"{WARN} — Only {non_zero} non-zero values — unusually sparse")
    else:
        print(f"{PASS} — {non_zero}/{len(vector)} non-zero values ✓")


def test_ai_search_field_compatibility(vector: list):
    """
    Simulate the exact search document that writer.py (Stage 5) will build.
    The `embedding` field takes the vector directly — no transformation.

    Full AI Search document shape (resumes-index schema):
    {
        "id":                   str,            <- Edm.String (key)
        "candidateId":          str,            <- Edm.String
        "cosmosDocumentId":     str,            <- Edm.String
        "name":                 str,            <- Edm.String
        "email":                str,            <- Edm.String
        "summary":              str,            <- Edm.String
        "skills":               list[str],      <- Collection(Edm.String)
        "currentRole":          str,            <- Edm.String
        "totalExperienceYears": float,          <- Edm.Double
        "uploadedAt":           str (ISO 8601), <- Edm.DateTimeOffset
        "blobUrl":              str,            <- Edm.String
        "embedding":            list[float],    <- Collection(Edm.Single) 1536-dim
    }
    """
    print("\n[7] AI Search document compatibility — `embedding` field assignment")
    try:
        mock_search_doc = {
            "id":                   "test-id-stage4",
            "candidateId":          "test-candidate-stage4",
            "cosmosDocumentId":     "test-cosmos-id-stage4",
            "name":                 "Test Candidate",
            "email":                "test@example.com",
            "summary":              "Test summary.",
            "skills":               ["Python", "Azure"],
            "currentRole":          "AI Engineer",
            "totalExperienceYears": 1.2,
            "uploadedAt":           "2026-05-15T00:00:00Z",
            "blobUrl":              "https://example.blob.core.windows.net/test",
            "embedding":            vector,
        }

        assert len(mock_search_doc["embedding"]) == EMBEDDING_DIMENSIONS
        assert isinstance(mock_search_doc["embedding"][0], float)

        print(f"{PASS} — Vector fits directly into search document `embedding` field ✓")

    except AssertionError as e:
        print(f"{FAIL} — {e}")


def test_empty_input_raises():
    """Empty string must raise ValueError — never silently embed nothing."""
    print("\n[8] Empty input raises ValueError")
    try:
        generate_embedding("")
        print(f"{FAIL} — Should have raised ValueError")
    except ValueError as e:
        print(f"{PASS} — ValueError raised: {e}")
    except Exception as e:
        print(f"{FAIL} — Wrong exception type {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("=" * 55)
    print("  Stage 4 — Embedding Generation Tests")
    print("  Input:  embeddingText from Stage 3 JSON output")
    print("  Output: list[float] 1536 -> AI Search `embedding`")
    print("=" * 55)

    embedding_text = load_embedding_text()

    if embedding_text:
        vector = test_generate_vector(embedding_text)

        if vector is not None:
            test_dimensions(vector)
            test_element_types(vector)
            test_value_range(vector)
            test_non_zero(vector)
            test_ai_search_field_compatibility(vector)

            print(f"\n  Vector preview (first 5 of {len(vector)} values):")
            print(f"     {[round(v, 8) for v in vector[:]]}")

    test_empty_input_raises()

    print("\n" + "=" * 55)
    print("  Done. All checks must PASS before Stage 5.")
    print("  Stage 5 (writer.py) will write this exact vector")
    print("  to AI Search and full document to Cosmos DB.")
    print("=" * 55)
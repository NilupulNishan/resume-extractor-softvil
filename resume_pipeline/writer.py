"""
writer.py
---------
Stage 5 — Dual Write: Cosmos DB + AI Search

Writes candidate data to both stores in a single call.
Each store gets exactly the fields it needs — nothing more.

Cosmos DB  → full system of record (all fields, raw text, full JSON, embeddingText)
AI Search  → lightweight retrieval document (display fields + vector only)

Field ownership:
    COSMOS ONLY:  rawExtractedText, structuredJson, embeddingText, blobJsonUrl,
                  workExperience, education, certifications, projects, languages,
                  personalInfo (full), lastUpdatedAt
    SEARCH ONLY:  embedding (vector)
    BOTH:         id/candidateId, name, email, summary, skills (normalized),
                  currentRole, totalExperienceYears, uploadedAt, blobUrl

Partial failure handling:
    Cosmos fails  → raise immediately, nothing written to Search
    Cosmos ok, Search fails → update Cosmos processingStatus to "failed", raise
    Both ok → return result dict with cosmosDocumentId
"""

from datetime import datetime, timezone

from resume_pipeline.clients import cosmos_container, search_client


def write_candidate(
    candidate_id:    str,
    raw_text:        str,
    structured_json: dict,
    embedding_text:  str,
    vector:          list[float],
    sas_url:         str,
) -> dict:
    """
    Dual-write a candidate to Cosmos DB and AI Search.

    Args:
        candidate_id:    UUID4 string — shared key across both stores
        raw_text:        Original Document Intelligence output (Stage 2)
        structured_json: Normalized candidate data from GPT-4o (Stage 3)
        embedding_text:  Semantic summary string from GPT-4o (Stage 3)
        vector:          1536-dim float list from text-embedding-3-small (Stage 4)
        sas_url:         Signed blob URL from blob_service.py (Stage 1)

    Returns:
        {
            "candidateId":      str,
            "cosmosDocumentId": str,
            "status":           "completed"
        }

    Raises:
        Exception if either write fails.
        If Cosmos succeeds but Search fails, Cosmos processingStatus is
        updated to "failed" before raising so the record is not orphaned.
    """
    now = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Write to Cosmos DB ─────────────────────────────────────────────
    cosmos_doc = _build_cosmos_document(
        candidate_id, raw_text, structured_json, embedding_text, sas_url, now
    )

    try:
        cosmos_result = cosmos_container.upsert_item(cosmos_doc)
        cosmos_doc_id = cosmos_result["id"]
    except Exception as e:
        raise Exception(f"Cosmos DB write failed for candidate '{candidate_id}': {e}") from e

    # ── Step 2: Write to AI Search ─────────────────────────────────────────────
    search_doc = _build_search_document(
        candidate_id, cosmos_doc_id, structured_json, vector, sas_url, now
    )

    try:
        results = search_client.upload_documents(documents=[search_doc])
        result  = results[0]
        if not result.succeeded:
            raise Exception(f"AI Search rejected document: {result.error_message}")

    except Exception as e:
        # Cosmos write succeeded — mark it failed so it's not an orphaned "completed" record
        _mark_cosmos_failed(candidate_id, cosmos_doc_id, error=str(e))
        raise Exception(
            f"AI Search write failed for candidate '{candidate_id}': {e}\n"
            f"Cosmos DB record '{cosmos_doc_id}' marked as failed."
        ) from e

    # ── Step 3: Update processingStatus to completed ───────────────────────────
    _mark_cosmos_completed(candidate_id, cosmos_doc_id)

    return {
        "candidateId":      candidate_id,
        "cosmosDocumentId": cosmos_doc_id,
        "status":           "completed",
    }


# ── Document builders ──────────────────────────────────────────────────────────

def _build_cosmos_document(
    candidate_id:    str,
    raw_text:        str,
    structured_json: dict,
    embedding_text:  str,
    sas_url:         str,
    timestamp:       str,
) -> dict:
    """
    Build the full Cosmos DB document.
    `id` = candidateId — simplifies direct lookups by candidate.
    All structured fields are stored both at top level (for easy querying)
    and inside structuredJson (for full audit / reprocessing).
    """
    personal_info = structured_json.get("personalInfo", {})

    return {
        # ── Cosmos DB required fields ──────────────────────────────────────────
        "id":          candidate_id,    # Cosmos document id
        "candidateId": candidate_id,    # Partition key — must match /candidateId

        # ── Personal info (top-level for easy access) ──────────────────────────
        "personalInfo": personal_info,

        # ── Structured data arrays ─────────────────────────────────────────────
        "workExperience":  structured_json.get("workExperience",  []),
        "education":       structured_json.get("education",       []),
        "skills":          structured_json.get("skills",          {}),
        "certifications":  structured_json.get("certifications",  []),
        "projects":        structured_json.get("projects",        []),
        "languages":       structured_json.get("languages",       []),

        # ── Derived summary fields (top-level for easy querying) ───────────────
        "currentRole":            structured_json.get("currentRole"),
        "currentCompany":         structured_json.get("currentCompany"),
        "totalExperienceYears":   structured_json.get("totalExperienceYears"),
        "summary":                structured_json.get("summary"),

        # ── Raw pipeline outputs (audit + reprocessing) ────────────────────────
        "rawExtractedText": raw_text,
        "structuredJson":   structured_json,
        "embeddingText":    embedding_text,   # Text that was embedded — audit trail

        # ── Blob references ────────────────────────────────────────────────────
        "blobUrl":     sas_url,   # Signed URL to original CV file
        "blobJsonUrl": None,      # Phase 2: reference to structured JSON in blob storage

        # ── Metadata ──────────────────────────────────────────────────────────
        "uploadedAt":       timestamp,
        "lastUpdatedAt":    timestamp,
        "processingStatus": "processing",   # Updated to "completed" after Search write
    }


def _build_search_document(
    candidate_id:    str,
    cosmos_doc_id:   str,
    structured_json: dict,
    vector:          list[float],
    sas_url:         str,
    timestamp:       str,
) -> dict:
    """
    Build the lightweight AI Search document.
    Only display fields + vector. No raw text, no full JSON, no embeddingText.

    Field types must match resumes-index schema exactly:
        skills               → Collection(Edm.String) — list of strings
        totalExperienceYears → Edm.Double             — float or None
        uploadedAt           → Edm.DateTimeOffset     — ISO 8601 string
        embedding            → Collection(Edm.Single) — list of floats, 1536 dims
    """
    personal_info  = structured_json.get("personalInfo", {})
    skills_data    = structured_json.get("skills", {})

    # Collection(Edm.String) — use normalized skill list; fall back to raw if empty
    normalized_skills = skills_data.get("normalized") or skills_data.get("raw") or []

    # Edm.Double — must be float or None (not int)
    experience_years = structured_json.get("totalExperienceYears")
    if experience_years is not None:
        experience_years = float(experience_years)

    return {
        # ── Key + link fields ─────────────────────────────────────────────────
        "id":               candidate_id,    # Key field (Edm.String)
        "candidateId":      candidate_id,    # FK → Cosmos DB
        "cosmosDocumentId": cosmos_doc_id,   # Direct Cosmos lookup on click

        # ── Recruiter card display fields ─────────────────────────────────────
        "name":         personal_info.get("fullName"),
        "email":        personal_info.get("email"),
        "summary":      structured_json.get("summary"),          # Edm.String
        "skills":       normalized_skills,                        # Collection(Edm.String)
        "currentRole":  structured_json.get("currentRole"),      # Edm.String
        "totalExperienceYears": experience_years,                 # Edm.Double

        # ── Temporal + blob ───────────────────────────────────────────────────
        "uploadedAt": timestamp,    # Edm.DateTimeOffset — ISO 8601
        "blobUrl":    sas_url,      # Edm.String — signed URL

        # ── Vector field ──────────────────────────────────────────────────────
        "embedding": vector,        # Collection(Edm.Single) — 1536 floats
    }


# ── Status update helpers ──────────────────────────────────────────────────────

def _mark_cosmos_completed(candidate_id: str, cosmos_doc_id: str) -> None:
    """Patch processingStatus to 'completed' after both writes succeed."""
    try:
        cosmos_container.patch_item(
            item=cosmos_doc_id,
            partition_key=candidate_id,
            patch_operations=[
                {"op": "replace", "path": "/processingStatus", "value": "completed"},
                {"op": "replace", "path": "/lastUpdatedAt",    "value": datetime.now(timezone.utc).isoformat()},
            ],
        )
    except Exception as e:
        # Non-fatal — document is written, status just didn't update
        print(f"  ⚠️  Could not mark Cosmos document as completed: {e}")


def _mark_cosmos_failed(candidate_id: str, cosmos_doc_id: str, error: str) -> None:
    """Patch processingStatus to 'failed' if Search write fails after Cosmos write."""
    try:
        cosmos_container.patch_item(
            item=cosmos_doc_id,
            partition_key=candidate_id,
            patch_operations=[
                {"op": "replace", "path": "/processingStatus", "value": "failed"},
                {"op": "replace", "path": "/lastUpdatedAt",    "value": datetime.now(timezone.utc).isoformat()},
            ],
        )
    except Exception as patch_error:
        print(f"  ⚠️  Could not mark Cosmos document as failed: {patch_error}")
        print(f"     Original Search error: {error}")
"""
test_structurer.py
------------------
Stage 3 gate test — validates GPT-4o structured extraction.

Uses the same fixture file from Stage 2 (tests/fixtures/).
Runs the full chain: file → extract_text → structure_resume
Validates every required schema field and prints a human-readable summary
so you can visually confirm GPT-4o understood the candidate correctly.

Usage:
    python tests/test_structurer.py
"""

import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_pipeline.extractor  import extract_text
from resume_pipeline.structurer import structure_resume

PASS     = "  ✅ PASS"
FAIL     = "  ❌ FAIL"
WARN     = "  ⚠️  WARN"
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

# All top-level keys that must be present in structuredJson
REQUIRED_KEYS = [
    "personalInfo",
    "summary",
    "workExperience",
    "education",
    "skills",
    "certifications",
    "projects",
    "languages",
    "currentRole",
    "totalExperienceYears",
]


def find_first_fixture() -> dict | None:
    for fname in os.listdir(FIXTURES):
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if ext in ("pdf", "docx"):
            return {"path": os.path.join(FIXTURES, fname), "name": fname, "extension": ext}
    return None


def test_extraction_chain():
    """Stage 2 → Stage 3: extract then structure."""
    print("\n[1] Run Stage 2 → Stage 3 chain on fixture file")
    fixture = find_first_fixture()

    if not fixture:
        print(f"{FAIL} — No fixture file found in tests/fixtures/")
        return None, None

    print(f"         Using: {fixture['name']}")

    try:
        with open(fixture["path"], "rb") as f:
            file_bytes = f.read()

        # Stage 2
        raw_text = extract_text(file_bytes, fixture["extension"])
        print(f"         Stage 2: extracted {len(raw_text):,} characters ✓")

        # Stage 3
        result = structure_resume(raw_text)
        print(f"{PASS} — GPT-4o call succeeded")
        return result["structuredJson"], result["embeddingText"]

    except Exception as e:
        print(f"{FAIL} — {e}")
        return None, None


def test_schema_completeness(structured_json: dict):
    """Every required key must be present."""
    print("\n[2] Schema completeness — all required keys present")
    missing = [k for k in REQUIRED_KEYS if k not in structured_json]

    if missing:
        print(f"{FAIL} — Missing keys: {missing}")
    else:
        print(f"{PASS} — All {len(REQUIRED_KEYS)} required keys present")


def test_personal_info(structured_json: dict):
    """personalInfo must have at least fullName and one contact field."""
    print("\n[3] personalInfo — name and contact")
    info = structured_json.get("personalInfo", {})

    name  = info.get("fullName")
    email = info.get("email")
    phone = info.get("phone")

    if not name:
        print(f"{FAIL} — fullName is missing or null")
        return

    contact = email or phone
    if not contact:
        print(f"{WARN} — No email or phone extracted — check resume content")
    else:
        print(f"{PASS} — Name: '{name}' | Email: {email} | Phone: {phone}")


def test_work_experience(structured_json: dict):
    print("\n[4] workExperience — at least one entry with required fields")
    experience = structured_json.get("workExperience", [])

    if not experience:
        print(f"{WARN} — No work experience found — may be a student resume")
        return

    entry = experience[0]
    issues = [f for f in ["company", "title"] if not entry.get(f)]
    if issues:
        print(f"{WARN} — First entry missing: {issues}")
    else:
        print(f"{PASS} — {len(experience)} role(s). Latest: '{entry['title']}' at '{entry['company']}'")


def test_skills(structured_json: dict):
    print("\n[5] skills — raw and normalized lists populated")
    skills = structured_json.get("skills", {})
    raw_skills  = skills.get("raw", [])
    norm_skills = skills.get("normalized", [])

    if not raw_skills:
        print(f"{FAIL} — No raw skills extracted")
    elif not norm_skills:
        print(f"{WARN} — Normalized skills empty — raw has {len(raw_skills)} items")
    else:
        preview = ", ".join(norm_skills[:8])
        print(f"{PASS} — {len(raw_skills)} raw / {len(norm_skills)} normalized. Preview: {preview}")


def test_experience_years(structured_json: dict):
    print("\n[6] totalExperienceYears — must be a number")
    years = structured_json.get("totalExperienceYears")

    if years is None:
        print(f"{WARN} — totalExperienceYears is null — GPT-4o could not infer")
    elif not isinstance(years, (int, float)):
        print(f"{FAIL} — Expected number, got: {type(years).__name__} = {years}")
    else:
        print(f"{PASS} — {years} years of experience")


def test_embedding_text(embedding_text: str):
    print("\n[7] embeddingText — quality check")

    if not embedding_text or not embedding_text.strip():
        print(f"{FAIL} — embeddingText is empty")
        return

    word_count     = len(embedding_text.split())
    sentence_count = embedding_text.count(".") + embedding_text.count("!")

    if word_count < 20:
        print(f"{FAIL} — Too short ({word_count} words) — GPT-4o did not generate a real summary")
        return

    if word_count > 200:
        print(f"{WARN} — Very long ({word_count} words) — should be 2–3 concise sentences")

    print(f"{PASS} — {word_count} words, ~{sentence_count} sentences")
    print(f"\n         ── embeddingText (this goes to vector search) ──")
    print(f"         {embedding_text}")
    print(f"         ──────────────────────────────────────────────────")


def print_candidate_summary(structured_json: dict):
    """Human-readable print of what GPT-4o understood — visual confirmation."""
    print("\n" + "─" * 55)
    print("  GPT-4o Extracted — Candidate Summary")
    print("─" * 55)

    info = structured_json.get("personalInfo", {})
    print(f"  Name:        {info.get('fullName', 'N/A')}")
    print(f"  Email:       {info.get('email', 'N/A')}")
    print(f"  Location:    {info.get('location', 'N/A')}")
    print(f"  LinkedIn:    {info.get('linkedIn', 'N/A')}")
    print(f"  Current:     {structured_json.get('currentRole', 'N/A')}")
    print(f"  Experience:  {structured_json.get('totalExperienceYears', 'N/A')} years")

    skills = structured_json.get("skills", {}).get("normalized", [])
    print(f"  Top Skills:  {', '.join(skills[:10])}")

    edu = structured_json.get("education", [])
    if edu:
        print(f"  Education:   {edu[0].get('degree')} — {edu[0].get('institution')}")

    certs = structured_json.get("certifications", [])
    print(f"  Certs:       {len(certs)} found")
    print(f"  Projects:    {len(structured_json.get('projects', []))} found")
    print("─" * 55)


if __name__ == "__main__":
    print("=" * 55)
    print("  Stage 3 — GPT-4o Structuring Tests")
    print("=" * 55)

    structured_json, embedding_text = test_extraction_chain()

    if structured_json is not None:
        test_schema_completeness(structured_json)
        test_personal_info(structured_json)
        test_work_experience(structured_json)
        test_skills(structured_json)
        test_experience_years(structured_json)
        test_embedding_text(embedding_text)
        print_candidate_summary(structured_json)

        # Save full JSON to file so you can inspect it
        output_path = os.path.join(os.path.dirname(__file__), "fixtures", "last_structured_output.json")
        with open(output_path, "w") as f:
            json.dump({"structuredJson": structured_json, "embeddingText": embedding_text}, f, indent=2)
        print(f"\n  💾 Full output saved → tests/fixtures/last_structured_output.json")

    print("\n" + "=" * 55)
    print("  Done. All checks must PASS before Stage 4.")
    print("=" * 55)
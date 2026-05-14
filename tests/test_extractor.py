"""
test_extractor.py
-----------------
Stage 2 gate test — validates Document Intelligence text extraction.

⚠️  IMPORTANT: This test requires a real resume file.
    Place at least one real resume in:  tests/fixtures/
    Supported:  any_resume.pdf  or  any_resume.docx

    You can use any CV — your own, a sample from the internet, etc.
    The test does NOT upload to blob storage — it sends bytes directly
    to Document Intelligence, matching how the pipeline works.

Usage:
    python tests/test_extractor.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_pipeline.extractor import extract_text

PASS     = "  ✅ PASS"
FAIL     = "  ❌ FAIL"
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def find_fixture_files() -> list[dict]:
    """Scan tests/fixtures/ for supported resume files."""
    if not os.path.exists(FIXTURES):
        return []

    files = []
    for fname in os.listdir(FIXTURES):
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if ext in ("pdf", "docx"):
            files.append({
                "path":      os.path.join(FIXTURES, fname),
                "name":      fname,
                "extension": ext,
            })
    return files


def test_fixture_files_exist():
    print("\n[1] Fixture files present in tests/fixtures/")
    files = find_fixture_files()
    if files:
        print(f"{PASS} — Found {len(files)} file(s):")
        for f in files:
            size_kb = os.path.getsize(f["path"]) // 1024
            print(f"         • {f['name']}  ({size_kb} KB)")
    else:
        print(f"{FAIL} — No PDF or DOCX files found in tests/fixtures/")
        print("         Create the folder and add at least one real resume:")
        print("         mkdir tests/fixtures")
        print("         Then copy a PDF or DOCX resume into it.")
    return files


def test_extraction(file_info: dict):
    fname = file_info["name"]
    ext   = file_info["extension"]

    print(f"\n[2] Extract text — {fname}")
    try:
        with open(file_info["path"], "rb") as f:
            file_bytes = f.read()

        raw_text = extract_text(file_bytes, ext)

        # Gate checks
        assert isinstance(raw_text, str),      "Output must be a string"
        assert len(raw_text) > 100,            f"Output too short ({len(raw_text)} chars) — likely empty or corrupted file"
        assert raw_text.strip() != "",         "Output must not be empty whitespace"

        print(f"{PASS} — Extracted {len(raw_text):,} characters")
        print(f"\n         ── First 400 characters of extracted text ──")
        print(f"         {raw_text[:400].replace(chr(10), ' | ')}")
        print(f"         ────────────────────────────────────────────")

        return raw_text

    except Exception as e:
        print(f"{FAIL} — {e}")
        return None


def test_text_quality(raw_text: str, fname: str):
    """
    Soft quality checks — these warn but don't hard-fail.
    A good extraction should pass all of these.
    """
    print(f"\n[3] Text quality checks — {fname}")
    issues = []

    if len(raw_text) < 500:
        issues.append(f"Very short output ({len(raw_text)} chars) — verify the resume has real content")

    garbage_ratio = sum(1 for c in raw_text if ord(c) > 127) / max(len(raw_text), 1)
    if garbage_ratio > 0.1:
        issues.append(f"High non-ASCII ratio ({garbage_ratio:.1%}) — possible encoding issue")

    line_count = len([l for l in raw_text.splitlines() if l.strip()])
    if line_count < 10:
        issues.append(f"Only {line_count} non-empty lines — layout extraction may have failed")

    if issues:
        for issue in issues:
            print(f"  ⚠️  WARNING: {issue}")
    else:
        print(f"{PASS} — {len(raw_text):,} chars, {line_count} lines, clean encoding")


def test_unsupported_format():
    print(f"\n[4] Unsupported file format raises ValueError")
    try:
        extract_text(b"fake content", "txt")
        print(f"{FAIL} — Should have raised ValueError")
    except ValueError as e:
        print(f"{PASS} — ValueError raised correctly: {e}")
    except Exception as e:
        print(f"{FAIL} — Wrong exception type: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("=" * 55)
    print("  Stage 2 — Document Intelligence Extraction Tests")
    print("=" * 55)

    # Check fixtures exist first
    files = test_fixture_files_exist()

    if not files:
        print("\n  ⛔  Cannot continue without a fixture file.")
        print("     Add a real resume to tests/fixtures/ and re-run.")
    else:
        # Run extraction on each fixture file found
        for file_info in files:
            raw_text = test_extraction(file_info)
            if raw_text:
                test_text_quality(raw_text, file_info["name"])

    # Always run format validation test
    test_unsupported_format()

    print("\n" + "=" * 55)
    print("  Done. All checks must PASS before Stage 3.")
    print("=" * 55)
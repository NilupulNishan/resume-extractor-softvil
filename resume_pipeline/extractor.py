"""
extractor.py
------------
Stage 2 — Document Intelligence

Takes raw CV file bytes (PDF or DOCX) and extracts clean, ordered text
using Azure Document Intelligence with the `prebuilt-read` model.

Why prebuilt-read:
  - Handles multi-column resume layouts correctly
  - Preserves reading order across sections
  - Works with both PDF and DOCX
  - Better than naive PDF parsers on real-world resume formatting

Input:  file bytes + content type string
Output: clean raw text string → passed directly to GPT-4o in Stage 3
"""

from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

from resume_pipeline.clients import document_intelligence_client

# The model to use — do not change this without re-validating output quality
DOCUMENT_MODEL = "prebuilt-read"

# Map file extensions to MIME types expected by Document Intelligence
CONTENT_TYPE_MAP = {
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def extract_text(file_bytes: bytes, file_extension: str) -> str:
    """
    Extract clean raw text from a CV file using Document Intelligence prebuilt-read.

    This is a synchronous blocking call — Document Intelligence processes the
    file and returns when complete. Typical latency: 2–8 seconds per resume.

    Args:
        file_bytes:     Raw bytes of the uploaded CV (PDF or DOCX)
        file_extension: 'pdf' or 'docx' (without dot)

    Returns:
        A single clean string containing all extracted text, pages joined with
        double newlines to preserve section separation.

    Raises:
        ValueError:  If file_extension is not supported
        Exception:   If Document Intelligence call fails
    """
    ext = file_extension.lower().strip(".")

    if ext not in CONTENT_TYPE_MAP:
        raise ValueError(
            f"Unsupported file type: '{ext}'. Supported types: {list(CONTENT_TYPE_MAP.keys())}"
        )

    # Send bytes directly — no temp files, no blob URL needed
    poller = document_intelligence_client.begin_analyze_document(
        model_id=DOCUMENT_MODEL,
        body=AnalyzeDocumentRequest(bytes_source=file_bytes),
        content_type="application/json",
    )

    result = poller.result()

    # result.content is the full extracted text in reading order
    # It is the cleanest single output — paragraphs, lines, words all merged
    raw_text = result.content or ""

    if not raw_text.strip():
        raise ValueError("Document Intelligence returned empty content. Check the uploaded file.")

    return raw_text.strip()
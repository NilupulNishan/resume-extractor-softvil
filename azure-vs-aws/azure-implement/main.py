"""
main.py — CLI entry point for the CV Extractor.

Architecture rule: this file is an orchestrator only.
- No business logic here
- No Azure types here
- Just: parse args → call extractor → call output modules

Usage:
    python main.py resume.pdf
    python main.py resume.pdf --output ./results/john.json
    python main.py candidate.jpg --output extracted.json
"""

import argparse
import sys
from pathlib import Path

from azure.core.exceptions import HttpResponseError

from extractor import analyze_cv
from output import print_profile, save_json
from config import settings


SUPPORTED = {
    ".pdf", ".docx", ".doc",
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".heif", ".heic"
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cv_extractor",
        description="Extract structured data from any CV/resume using Azure Document Intelligence.",
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the CV file (PDF, DOCX, JPG, PNG, …)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output JSON path (default: <OUTPUT_DIR>/<filename>_extracted.json)"
    )
    return parser.parse_args()


def resolve_output(input_path: Path, override: Path | None) -> Path:
    if override:
        return override
    stem = input_path.stem
    return settings.output_dir / f"{stem}_extracted.json"


def main() -> None:
    args = parse_args()
    input_path: Path = args.file.resolve()

    # ── Validate input ────────────────────────────────────────────────────────
    if not input_path.exists():
        print(f"[error] File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if input_path.suffix.lower() not in SUPPORTED:
        print(f"[error] Unsupported file type: {input_path.suffix}", file=sys.stderr)
        print(f"  Supported: {', '.join(sorted(SUPPORTED))}", file=sys.stderr)
        sys.exit(1)

    output_path = resolve_output(input_path, args.output)

    print(f"\n  File   : {input_path.name}")
    print(f"  Model  : {settings.model}")
    print(f"  Output : {output_path}")
    print(f"  Sending to Azure…\n")

    # ── Extract ───────────────────────────────────────────────────────────────
    try:
        profile = analyze_cv(input_path)
    except HttpResponseError as e:
        print(f"[azure error] {e.error.code}: {e.error.message}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[error] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Output ────────────────────────────────────────────────────────────────
    print_profile(profile)

    saved_path = save_json(profile, output_path)
    print(f"  JSON saved → {saved_path}\n")


if __name__ == "__main__":
    main()
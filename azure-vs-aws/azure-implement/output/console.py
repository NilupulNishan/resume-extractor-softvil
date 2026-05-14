"""
output/console.py — Pretty-prints a CandidateProfile to the terminal.

Single responsibility: visual presentation only.
No business logic, no file I/O.
"""

import sys
from extractor.models import CandidateProfile

# ANSI colors — auto-disabled when not a TTY (e.g. piped to a file)
_IS_TTY = sys.stdout.isatty()

_C = {
    "header":  "\033[1;36m",
    "section": "\033[1;33m",
    "label":   "\033[0;90m",
    "value":   "\033[0;97m",
    "success": "\033[0;32m",
    "error":   "\033[0;31m",
    "reset":   "\033[0m",
}

def _c(key: str, text: str) -> str:
    return f"{_C[key]}{text}{_C['reset']}" if _IS_TTY else text

def _divider():
    print(_c("header", "━" * 62))

def _section(title: str):
    print(_c("section", f"\n  {title}"))

def _row(label: str, value: str):
    print(f"    {_c('label', label.ljust(12))}  {_c('value', value)}")


def print_profile(profile: CandidateProfile) -> None:
    """Print a full CandidateProfile to stdout."""
    _divider()
    print(_c("header", f"  {profile.full_name or 'Unknown Candidate'}"))
    _divider()

    # Contact
    c = profile.contact
    if c.emails or c.phones or c.urls or c.address:
        _section("CONTACT")
        for email   in c.emails:  _row("Email",   email)
        for phone   in c.phones:  _row("Phone",   phone)
        for url     in c.urls:    _row("URL",     url)
        if c.address:             _row("Address", c.address)

    # Summary
    if profile.summary:
        _section("SUMMARY")
        for chunk in [profile.summary[i:i+72] for i in range(0, len(profile.summary), 72)]:
            print(f"    {_c('value', chunk)}")

    # Skills
    if profile.skills:
        _section("SKILLS")
        for chunk in [profile.skills[i:i+5] for i in range(0, len(profile.skills), 5)]:
            print(f"    {_c('value', '  ·  '.join(chunk))}")

    # Languages
    if profile.languages:
        _section("LANGUAGES")
        print(f"    {_c('value', '  ·  '.join(profile.languages))}")

    # Work Experience
    if profile.experience:
        _section("WORK EXPERIENCE")
        for exp in profile.experience:
            role    = exp.role    or "—"
            company = exp.company or "—"
            dates   = f"{exp.start or ''} → {exp.end or 'present'}" if exp.start else ""
            loc     = f"  {exp.location}" if exp.location else ""
            print(f"    {_c('value', role)}  {_c('label', '·')}  {_c('value', company)}")
            if dates or loc:
                print(f"      {_c('label', dates + loc)}")
            if exp.description:
                snippet = exp.description[:120] + ("…" if len(exp.description) > 120 else "")
                print(f"      {_c('label', snippet)}")
            print()

    # Education
    if profile.education:
        _section("EDUCATION")
        for edu in profile.education:
            degree = edu.degree or "—"
            field  = f" in {edu.field_of_study}" if edu.field_of_study else ""
            inst   = edu.institution or "—"
            dates  = f"{edu.start or ''} → {edu.end or ''}" if edu.start else ""
            print(f"    {_c('value', degree + field)}  {_c('label', '·')}  {_c('value', inst)}")
            if dates:
                print(f"      {_c('label', dates)}")
            if edu.gpa:
                print(f"      {_c('label', 'GPA: ')}{_c('value', edu.gpa)}")
            print()

    # Meta
    _section("META")
    _row("Model",      profile.meta.model      or "—")
    _row("Confidence", f"{profile.meta.confidence * 100:.1f}%" if profile.meta.confidence else "—")
    _row("Extracted",  profile.meta.extracted_at or "—")
    _row("Source",     profile.meta.source_file  or "—")

    print()
    _divider()
    print()
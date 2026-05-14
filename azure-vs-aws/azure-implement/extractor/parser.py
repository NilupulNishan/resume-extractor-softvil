"""
extractor/parser.py — Maps raw Azure Document Intelligence result → CandidateProfile.

Architecture rule:
    Azure types stay inside this file.
    Everything returned is a plain CandidateProfile (our own schema).
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.exceptions import HttpResponseError

from config import settings
from extractor.client import get_client
from extractor.models import (
    CandidateProfile,
    ContactInfo,
    Education,
    Experience,
    Meta,
)


# ── Low-level field helpers ───────────────────────────────────────────────────

def _str(doc_field) -> Optional[str]:
    """Safely pull a string value from an Azure DocumentField."""
    if doc_field is None:
        return None
    return getattr(doc_field, "value_string", None) or getattr(doc_field, "content", None) or None

def _obj(doc_field) -> dict:
    """Return the value_object dict of a DocumentField, or {}."""
    if doc_field is None:
        return {}
    return getattr(doc_field, "value_object", None) or {}

def _arr(doc_field) -> list:
    """Return the value_array list of a DocumentField, or []."""
    if doc_field is None:
        return []
    return getattr(doc_field, "value_array", None) or []

def _fmt_date(doc_field) -> Optional[str]:
    """Format an Azure date field (year/month/day) to YYYY-MM-DD string."""
    if doc_field is None:
        return None
    d = getattr(doc_field, "value_date", None)
    if d is None:
        return _str(doc_field)
    year  = getattr(d, "year",  None)
    month = getattr(d, "month", None)
    day   = getattr(d, "day",   None)
    if year and month and day:
        return f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
    if year and month:
        return f"{year}-{str(month).zfill(2)}"
    if year:
        return str(year)
    return None

def _address(doc_field) -> Optional[str]:
    """Flatten an Azure address field into a readable string."""
    if doc_field is None:
        return None
    v = getattr(doc_field, "value_address", None)
    if v:
        parts = [
            getattr(v, "house_number", None),
            getattr(v, "road",         None),
            getattr(v, "city",         None),
            getattr(v, "state",        None),
            getattr(v, "postal_code",  None),
            getattr(v, "country_region", None),
        ]
        joined = ", ".join(p for p in parts if p)
        return joined or _str(doc_field)
    return _str(doc_field)


# ── Section parsers ───────────────────────────────────────────────────────────

def _parse_contact(contact_field) -> ContactInfo:
    obj = _obj(contact_field)
    info = ContactInfo()

    emails = _arr(obj.get("Emails"))
    info.emails = [_str(e) for e in emails if _str(e)]

    phones = _arr(obj.get("PhoneNumbers"))
    info.phones = [_str(p) for p in phones if _str(p)]

    urls = _arr(obj.get("Urls"))
    info.urls = [_str(u) for u in urls if _str(u)]

    info.address = _address(obj.get("Address"))
    return info


def _parse_experience(exp_list_field) -> list[Experience]:
    results = []
    for item in _arr(exp_list_field):
        obj = _obj(item)
        results.append(Experience(
            role=        _str(obj.get("JobTitle")),
            company=     _str(obj.get("Employer")),
            location=    _address(obj.get("Location")) or _str(obj.get("Location")),
            start=       _fmt_date(obj.get("StartDate")),
            end=         _fmt_date(obj.get("EndDate")),
            description= _str(obj.get("Description")),
        ))
    return results


def _parse_education(edu_list_field) -> list[Education]:
    results = []
    for item in _arr(edu_list_field):
        obj = _obj(item)
        results.append(Education(
            degree=         _str(obj.get("Degree")),
            field_of_study= _str(obj.get("FieldOfStudy")),
            institution=    _str(obj.get("SchoolName")),
            start=          _fmt_date(obj.get("StartDate")),
            end=            _fmt_date(obj.get("EndDate")),
            gpa=            _str(obj.get("GPA")),
            description=    _str(obj.get("Description")),
        ))
    return results


def _parse_skills(skills_field) -> list[str]:
    return [_str(s) for s in _arr(skills_field) if _str(s)]


def _parse_languages(lang_field) -> list[str]:
    return [_str(l) for l in _arr(lang_field) if _str(l)]


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_cv(file_path: Path) -> CandidateProfile:
    """
    Send a CV file to Azure Document Intelligence and return a CandidateProfile.

    Args:
        file_path: Path to the CV file (PDF, DOCX, image, …).

    Returns:
        CandidateProfile with all extracted fields.

    Raises:
        HttpResponseError: Azure API error.
        FileNotFoundError: File does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    client = get_client()

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    try:
        poller = client.begin_analyze_document(
            model_id=settings.model,
            body=AnalyzeDocumentRequest(bytes_source=file_bytes),
        )
        result = poller.result()
    except HttpResponseError as e:
        raise

    if not result.documents:
        return CandidateProfile(
            meta=Meta(
                model=settings.model,
                extracted_at=datetime.utcnow().isoformat() + "Z",
                source_file=file_path.name,
            )
        )

    doc    = result.documents[0]
    fields = doc.fields or {}

    # ── Name ──
    name_obj   = _obj(fields.get("Name"))
    first_name = _str(name_obj.get("FirstName"))
    last_name  = _str(name_obj.get("LastName"))
    full_name  = " ".join(p for p in [first_name, last_name] if p) or _str(fields.get("Name"))

    return CandidateProfile(
        full_name=  full_name,
        first_name= first_name,
        last_name=  last_name,
        summary=    _str(fields.get("Summary")),
        contact=    _parse_contact(fields.get("ContactInformation")),
        skills=     _parse_skills(fields.get("Skills")),
        languages=  _parse_languages(fields.get("Languages")),
        experience= _parse_experience(fields.get("WorkExperience")),
        education=  _parse_education(fields.get("Education")),
        meta=Meta(
            model=        doc.doc_type,
            confidence=   round(doc.confidence, 4) if doc.confidence else None,
            extracted_at= datetime.utcnow().isoformat() + "Z",
            source_file=  file_path.name,
        ),
    )
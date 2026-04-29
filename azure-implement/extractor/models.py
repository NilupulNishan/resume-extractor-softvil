from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ContactInfo:
    emails:  List[str] = field(default_factory=list)
    phones:  List[str] = field(default_factory=list)
    urls:    List[str] = field(default_factory=list)
    address: Optional[str] = None


@dataclass
class Experience:
    role:        Optional[str] = None
    company:     Optional[str] = None
    location:    Optional[str] = None
    start:       Optional[str] = None
    end:         Optional[str] = None
    description: Optional[str] = None


@dataclass
class Education:
    degree:      Optional[str] = None
    field_of_study: Optional[str] = None
    institution: Optional[str] = None
    start:       Optional[str] = None
    end:         Optional[str] = None
    gpa:         Optional[str] = None
    description: Optional[str] = None


@dataclass
class Meta:
    model:        Optional[str] = None
    confidence:   Optional[float] = None
    extracted_at: Optional[str] = None
    source_file:  Optional[str] = None


@dataclass
class CandidateProfile:
    full_name:  Optional[str] = None
    first_name: Optional[str] = None
    last_name:  Optional[str] = None
    summary:    Optional[str] = None
    contact:    ContactInfo = field(default_factory=ContactInfo)
    skills:     List[str] = field(default_factory=list)
    languages:  List[str] = field(default_factory=list)
    experience: List[Experience] = field(default_factory=list)
    education:  List[Education] = field(default_factory=list)
    meta:       Meta = field(default_factory=Meta)

    def to_dict(self) -> dict:
        """Serialize to a clean dict, dropping None/empty values."""
        import dataclasses

        def _clean(obj):
            if dataclasses.is_dataclass(obj):
                result = {}
                for f in dataclasses.fields(obj):
                    v = _clean(getattr(obj, f.name))
                    # Keep meta always; skip empty for everything else
                    if f.name == "meta" or v not in (None, [], {}):
                        result[f.name] = v
                return result
            if isinstance(obj, list):
                return [_clean(i) for i in obj]
            return obj

        return _clean(self)
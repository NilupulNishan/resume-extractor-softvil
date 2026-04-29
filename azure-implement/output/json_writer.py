import json
from pathlib import Path
 
from extractor.models import CandidateProfile
 
 
def save_json(profile: CandidateProfile, output_path: Path) -> Path:
    """
    Serialize profile to JSON and write to output_path.
 
    Returns the resolved output path so callers can log it.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
 
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2, default=str)
 
    return output_path.resolve()
 
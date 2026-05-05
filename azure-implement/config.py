import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (same folder as this file)
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path)


@dataclass(frozen=True)
class Settings:
    """Immutable settings object. Fail fast if required vars are missing."""
    endpoint: str
    key:      str
    model:    str
    output_dir: Path

    @classmethod
    def load(cls) -> "Settings":
        errors = []

        endpoint = os.getenv("AZURE_DI_ENDPOINT", "").strip().rstrip("/")
        key      = os.getenv("AZURE_DI_KEY",      "").strip()
        model    = os.getenv("AZURE_DI_MODEL",    "prebuilt-layout").strip()
        out_raw  = os.getenv("OUTPUT_DIR",         ".").strip()

        if not endpoint:
            errors.append("  AZURE_DI_ENDPOINT is not set")
        if not key:
            errors.append("  AZURE_DI_KEY is not set")

        if errors:
            print("\n[config error] Missing required environment variables:")
            for e in errors:
                print(e)
            print("\n  → Copy .env.example to .env and fill in your values.\n")
            sys.exit(1)

        output_dir = Path(out_raw)
        output_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            endpoint=endpoint,
            key=key,
            model=model,
            output_dir=output_dir,
        )


# Module-level singleton — import this everywhere
settings = Settings.load()
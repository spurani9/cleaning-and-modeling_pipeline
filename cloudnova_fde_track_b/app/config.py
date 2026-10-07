from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

@dataclass(frozen=True)
class Settings:
    raw_csv: Path = ROOT / "data" / "cloudnova_invoices.csv"
    artifact_dir: Path = ROOT / "artifacts"
    model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    base_url: Optional[str] = os.getenv("OPENAI_BASE_URL") or None

settings = Settings()

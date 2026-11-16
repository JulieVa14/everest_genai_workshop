import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    mode: str
    data_dir: Path
    api_key: str = field(repr=False)
    model: str
    embedding_model: str
    frontend_origin: str
    base_url: str = ""
    max_upload_bytes: int = 10 * 1024 * 1024
    retrieval_count: int = 5
    max_turns: int = 6
    timeout_seconds: float = 60
    max_output_tokens: int = 800

    def __post_init__(self):
        origin = urlsplit(self.frontend_origin)
        if (
            origin.scheme not in {"http", "https"}
            or origin.hostname not in {"localhost", "127.0.0.1", "::1"}
            or origin.username
            or origin.password
            or origin.path
            or origin.query
            or origin.fragment
        ):
            raise ValueError("FRONTEND_ORIGIN must be a single localhost origin without a path")
        endpoint = urlsplit(self.base_url)
        if self.base_url and (endpoint.scheme != "https" or not endpoint.hostname
                              or endpoint.username or endpoint.password or endpoint.query):
            raise ValueError("OPENAI_BASE_URL must be an https URL without credentials")
        if self.mode not in {"student", "solution"}:
            raise ValueError("WORKSHOP_MODE must be student or solution")
        if not (
            0 < self.max_upload_bytes <= 10 * 1024 * 1024
            and 1 <= self.retrieval_count <= 8
            and 1 <= self.max_turns <= 8
            and 0 < self.timeout_seconds <= 120
            and 1 <= self.max_output_tokens <= 1600
        ):
            raise ValueError("Workshop resource limits exceed supported bounds")


def load_settings() -> Settings:
    load_dotenv(ROOT / "backend" / ".env", override=False)
    mode = os.getenv("WORKSHOP_MODE", "student").lower()
    if mode not in {"student", "solution"}:
        raise ValueError("WORKSHOP_MODE must be student or solution")
    data_root = Path(os.getenv("WORKSHOP_DATA_DIR", str(ROOT / ".workshop-data" / "app")))
    data_dir = (data_root / mode).resolve()
    return Settings(
        mode=mode,
        data_dir=data_dir,
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-terra"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
    )

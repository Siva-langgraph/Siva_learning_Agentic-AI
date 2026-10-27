from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

def _load_env_file() -> None:
    path = Path(os.getenv("ENV_FILE", ".env"))
    if not path.is_file(): return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
_load_env_file()

@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    api_key: str = os.getenv("APP_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./commerce_demo.db")
    max_tool_rounds: int = max(1, min(8, int(os.getenv("MAX_TOOL_ROUNDS", "4"))))
    query_timeout_seconds: int = max(1, min(30, int(os.getenv("QUERY_TIMEOUT_SECONDS", "5"))))
    allowed_origins: tuple[str, ...] = tuple(x.strip() for x in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if x.strip())
settings = Settings()

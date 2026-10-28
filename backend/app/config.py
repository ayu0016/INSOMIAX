from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
_PROCESS_DSN_CONFIGURED = bool(os.getenv("RADIX_SUPABASE_READONLY_DSN", "").strip())
_DOTENV_DSN_CONFIGURED = bool((dotenv_values(ENV_FILE).get("RADIX_SUPABASE_READONLY_DSN") or "").strip())
load_dotenv(ENV_FILE)


def database_dsn_source() -> str:
    """Return safe provenance metadata without returning the DSN itself."""
    if _PROCESS_DSN_CONFIGURED:
        return "process_environment"
    if _DOTENV_DSN_CONFIGURED:
        return "repository_root_dotenv"
    return "none"


def _configured(value: str | None) -> str | None:
    candidate = (value or "").strip()
    upper = candidate.upper()
    placeholders = ("REPLACE", "PROJECT_REF", "DB_HOST", "READ_ONLY_USER", "<", ">")
    if not candidate or any(marker in upper for marker in placeholders):
        return None
    return candidate


@dataclass(frozen=True)
class Settings:
    readonly_dsn: str | None
    supabase_url: str | None
    supabase_anon_key: str | None
    staging_schema: str | None
    cors_origins: tuple[str, ...]

    @classmethod
    def from_environment(cls) -> "Settings":
        dsn = _configured(os.getenv("RADIX_SUPABASE_READONLY_DSN"))
        supabase_url = _configured(os.getenv("SUPABASE_URL"))
        anon_key = _configured(os.getenv("SUPABASE_ANON_KEY"))
        if supabase_url:
            supabase_url = supabase_url.rstrip("/")
        schema = os.getenv("RADIX_STAGING_SCHEMA", "").strip() or None
        origins = tuple(
            origin.strip().rstrip("/")
            for origin in os.getenv(
                "RADIX_CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        )
        return cls(
            readonly_dsn=dsn,
            supabase_url=supabase_url,
            supabase_anon_key=anon_key,
            staging_schema=schema,
            cors_origins=origins,
        )

    @property
    def database_configured(self) -> bool:
        return bool(self.readonly_dsn)

    @property
    def auth_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)


def get_settings() -> Settings:
    return Settings.from_environment()

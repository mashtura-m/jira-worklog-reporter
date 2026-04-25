from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)

    if required and not value:
        raise EnvironmentError(
            f"Missing required environment variable: {name}"
        )

    return value.strip() if value else ""


def _env_bool(name: str, default: bool = True) -> bool:
    return _env(name, str(default)).lower() in ("1", "true", "yes", "y")


def _env_path(name: str, default: str) -> Path:
    return Path(_env(name, default))


def _env_zone(name: str, default: str = "UTC") -> ZoneInfo:
    return ZoneInfo(_env(name, default))


# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Config:
    """Runtime configuration for Jira Worklog Reporter."""

    # ── Required ─────────────────────────────────────────────
    base_url: str = field(default_factory=lambda: _env("JIRA_BASE_URL", required=True))
    email: str = field(default_factory=lambda: _env("JIRA_EMAIL", required=True))
    api_token: str = field(default_factory=lambda: _env("JIRA_API_TOKEN", required=True))

    project: str = field(default_factory=lambda: _env("JIRA_PROJECT", required=True))
    start_date: str = field(default_factory=lambda: _env("JIRA_START_DATE", required=True))
    end_date: str = field(default_factory=lambda: _env("JIRA_END_DATE", required=True))

    # ── Optional ─────────────────────────────────────────────
    timezone: ZoneInfo = field(default_factory=lambda: _env_zone("REPORT_TIMEZONE"))
    output_file: Path = field(default_factory=lambda: _env_path("REPORT_OUTPUT_FILE", "worklog_report.xlsx"))
    cache_file: Path = field(default_factory=lambda: _env_path("CACHE_FILE", ".cache/worklogs_cache.json"))

    use_cache: bool = field(default_factory=lambda: _env_bool("USE_CACHE", True))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO").upper())

    # ── Factory ──────────────────────────────────────────────
    @classmethod
    def from_env(cls) -> "Config":
        return cls()
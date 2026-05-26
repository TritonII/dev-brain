"""
Dev Brain Settings
==================

Pydantic BaseSettings with safety guardrails:
- Database isolation check (hard-fail if pointing at a blocked database)
- Read-only mode flag
- Credential scrubbing in logs
"""

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings


class BrainSettings(BaseSettings):
    """Configuration for the Dev Brain knowledge graph."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"

    # Graphiti group_id for data isolation (all Brain nodes tagged with this)
    GRAPHITI_GROUP_ID: str = "dev_brain"

    # Gemini via Vertex AI (primary)
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Gemini API key (fallback)
    GEMINI_API_KEY: str = ""

    # Graphiti
    GRAPHITI_READ_ONLY: bool = False

    # Repo paths for backfill
    PRIMARY_REPO_PATH: str = ""
    SECONDARY_REPO_PATH: str = ""

    # Blocked database names — comma-separated via env var
    BLOCKED_DB_NAMES: str = ""

    @model_validator(mode="after")
    def validate_database_isolation(self) -> "BrainSettings":
        """Hard-fail if NEO4J_DATABASE points at a blocked database."""
        if not self.BLOCKED_DB_NAMES:
            return self

        blocked = frozenset(
            name.strip().lower()
            for name in self.BLOCKED_DB_NAMES.split(",")
            if name.strip()
        )
        db_lower = self.NEO4J_DATABASE.lower().strip()
        if db_lower in blocked:
            raise ValueError(
                f"FATAL: NEO4J_DATABASE='{self.NEO4J_DATABASE}' matches a blocked "
                f"database name. The Dev Brain MUST use a separate database. "
                f"Configure BLOCKED_DB_NAMES in .env to list production databases."
            )
        return self


class _CredentialFilter(logging.Filter):
    """Scrub sensitive values from log records."""

    _patterns: list[re.Pattern] = []

    def configure(self, settings: BrainSettings) -> None:
        self._patterns = []
        if settings.NEO4J_PASSWORD:
            self._patterns.append(re.compile(re.escape(settings.NEO4J_PASSWORD)))
        if settings.GEMINI_API_KEY:
            self._patterns.append(re.compile(re.escape(settings.GEMINI_API_KEY)))

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.msg)
        for pattern in self._patterns:
            msg = pattern.sub("***REDACTED***", msg)
        record.msg = msg
        return True


_credential_filter = _CredentialFilter()


@lru_cache(maxsize=1)
def get_settings() -> BrainSettings:
    """Get cached settings singleton. Configures credential scrubbing on first call."""
    settings = BrainSettings()

    # Install credential filter on root logger
    _credential_filter.configure(settings)
    logging.getLogger().addFilter(_credential_filter)

    return settings

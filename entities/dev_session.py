"""DevSession entity — a working session between a developer and an LLM assistant."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DevSession(BaseModel):
    """A working session between a developer and an LLM assistant (e.g. Claude Code)."""

    session_date: datetime = Field(description="Date the session occurred")
    session_summary: str = Field(description="High-level summary of what happened in this session")
    focus_area: str = Field(
        description="Primary technical area, e.g. 'backend API', 'frontend spec', 'data pipeline'"
    )
    outcome_status: Literal["productive", "blocked", "exploratory", "pivoted"] = Field(
        description=(
            "productive = clear forward progress; blocked = hit an unresolved issue; "
            "exploratory = research/ideation; pivoted = changed direction mid-session"
        )
    )
    participants: list[str] = Field(
        default_factory=list,
        description="e.g. ['Developer', 'Claude-Opus-4']",
    )

"""Artifact entity — a concrete output: spec, ADR, commit, PR, test result, file."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Artifact(BaseModel):
    """A concrete output: spec, ADR, commit, PR, test result, file."""

    artifact_type: Literal[
        "spec", "adr", "commit", "pr", "test_result", "code_file", "doc", "session_summary"
    ] = Field(description="Type of artifact")
    title: str = Field(description="Human-readable name")
    path: Optional[str] = Field(default=None, description="Repo-relative path if applicable")
    repo: Optional[str] = Field(default=None, description="Repository name, e.g. 'my-project'")
    commit_sha: Optional[str] = Field(default=None, description="Git commit SHA if applicable")
    artifact_created_at: datetime = Field(description="When the artifact was created")

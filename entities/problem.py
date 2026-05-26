"""Problem entity — an unresolved issue blocking progress."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Problem(BaseModel):
    """An unresolved issue blocking progress."""

    description: str = Field(description="What the problem is")
    status: Literal["open", "investigating", "resolved", "deferred", "wontfix"] = Field(
        description="Current status"
    )
    severity: Literal["critical", "high", "medium", "low"] = Field(
        description="Severity level"
    )
    first_observed: datetime = Field(description="When the problem was first observed")
    resolved_at: Optional[datetime] = Field(
        default=None, description="When the problem was resolved"
    )

"""Decision entity — an architectural or product decision with rationale."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Decision(BaseModel):
    """An architectural or product decision with rationale."""

    decision_text: str = Field(description="What was decided, in one sentence")
    rationale: str = Field(description="Why this decision was made")
    status: Literal["active", "superseded", "reversed", "deferred"] = Field(
        description="Current status of the decision"
    )
    decided_at: datetime = Field(description="When the decision was made")
    domain: Literal[
        "architecture",
        "extraction_pipeline",
        "frontend",
        "data_model",
        "infrastructure",
        "product",
        "sales",
        "compliance",
        "tooling",
    ] = Field(description="What area of the system this decision affects")

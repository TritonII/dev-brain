"""Experiment entity — an attempted approach with a measurable outcome."""

from datetime import datetime

from pydantic import BaseModel, Field


class Experiment(BaseModel):
    """An attempted approach with a measurable outcome."""

    hypothesis: str = Field(description="What we expected to happen")
    approach: str = Field(description="What we actually did")
    outcome: str = Field(description="What happened")
    success: bool = Field(description="Did the experiment validate the hypothesis?")
    metrics: dict = Field(
        default_factory=dict,
        description="Any numeric results, e.g. {'accuracy_delta': 0.12}",
    )
    run_at: datetime = Field(description="When the experiment was run")

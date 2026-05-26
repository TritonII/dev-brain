"""Concept entity — a cross-cutting idea or pattern used across the project."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Concept(BaseModel):
    """A cross-cutting idea or pattern used across the project."""

    # NOTE: 'name' is reserved by Graphiti's EntityNode — using 'concept_name' instead
    concept_name: str = Field(
        description="Canonical name, e.g. 'Event Sourcing', 'Circuit Breaker', 'two-pass prompting'"
    )
    definition: str = Field(
        description="What this concept means in the context of the project"
    )
    first_introduced: Optional[datetime] = Field(
        default=None, description="When this concept was first introduced"
    )

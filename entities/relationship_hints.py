"""
Canonical relationship types for Graphiti extraction.

These are seeded into the extraction prompt so Graphiti consistently
uses the same edge vocabulary when building the knowledge graph.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Supersedes(BaseModel):
    """New decision replaces an older one."""
    reason: Optional[str] = Field(default=None, description="Why the old decision was superseded")


class DerivedFrom(BaseModel):
    """Causal origin — an artifact derived from another, or a decision derived from a problem."""
    derivation_context: Optional[str] = Field(
        default=None, description="How the target was derived from the source"
    )


class Validates(BaseModel):
    """Evidence supports — an experiment validates a decision or concept."""
    confidence: Optional[str] = Field(
        default=None, description="How strongly the evidence supports (strong/moderate/weak)"
    )


class Contradicts(BaseModel):
    """Evidence refutes — an experiment contradicts a decision."""
    contradiction_detail: Optional[str] = Field(
        default=None, description="What specifically was contradicted"
    )


class TestedBy(BaseModel):
    """Inverse of VALIDATES/CONTRADICTS — a decision or concept was tested by an experiment."""
    test_date: Optional[datetime] = Field(default=None, description="When the test occurred")


class References(BaseModel):
    """Soft link between any two entities."""
    context: Optional[str] = Field(default=None, description="Why these are related")


class Blocks(BaseModel):
    """Dependency blocker — a problem blocks a decision or experiment."""
    blocking_since: Optional[datetime] = Field(
        default=None, description="When the blocker was identified"
    )


class EmergedFrom(BaseModel):
    """Provenance to source session — a decision or concept emerged from a dev session."""
    session_context: Optional[str] = Field(
        default=None, description="What part of the session produced this"
    )


class AppliesTo(BaseModel):
    """Concept used in context — a concept applies to a decision or problem."""
    application_detail: Optional[str] = Field(
        default=None, description="How the concept applies in this context"
    )


# Registry of all edge types for Graphiti extraction
EDGE_TYPES: dict[str, type[BaseModel]] = {
    "Supersedes": Supersedes,
    "DerivedFrom": DerivedFrom,
    "Validates": Validates,
    "Contradicts": Contradicts,
    "TestedBy": TestedBy,
    "References": References,
    "Blocks": Blocks,
    "EmergedFrom": EmergedFrom,
    "AppliesTo": AppliesTo,
}

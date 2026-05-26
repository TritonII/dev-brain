"""
Dev Brain Entity Types
======================

6 entity types + 9 edge types for Graphiti extraction.
All classes are standard Pydantic BaseModel — no special base class required.

Reserved Graphiti attribute names (NEVER use in entity schemas):
  uuid, name, group_id, labels, created_at, summary, attributes, name_embedding
"""

from pydantic import BaseModel

from .dev_session import DevSession
from .decision import Decision
from .artifact import Artifact
from .problem import Problem
from .experiment import Experiment
from .concept import Concept
from .relationship_hints import EDGE_TYPES

# Entity type registry — passed to graphiti.add_episode(entity_types=...)
ENTITY_TYPES: dict[str, type[BaseModel]] = {
    "DevSession": DevSession,
    "Decision": Decision,
    "Artifact": Artifact,
    "Problem": Problem,
    "Experiment": Experiment,
    "Concept": Concept,
}

__all__ = [
    "DevSession",
    "Decision",
    "Artifact",
    "Problem",
    "Experiment",
    "Concept",
    "ENTITY_TYPES",
    "EDGE_TYPES",
]

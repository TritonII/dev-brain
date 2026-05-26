"""
Tests for entity type definitions.

Validates:
- All 6 entity types are valid Pydantic models
- No entity uses Graphiti reserved attribute names
- Entity registry is complete
- Models serialize/deserialize correctly
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from entities import (
    ENTITY_TYPES,
    EDGE_TYPES,
    DevSession,
    Decision,
    Artifact,
    Problem,
    Experiment,
    Concept,
)

# Reserved by Graphiti's EntityNode — entities must NOT use these field names
GRAPHITI_RESERVED = {"uuid", "name", "group_id", "labels", "created_at", "summary", "attributes", "name_embedding"}


class TestEntityRegistry:
    def test_all_six_types_registered(self):
        assert len(ENTITY_TYPES) == 6
        expected = {"DevSession", "Decision", "Artifact", "Problem", "Experiment", "Concept"}
        assert set(ENTITY_TYPES.keys()) == expected

    def test_all_types_are_pydantic_models(self):
        for name, cls in ENTITY_TYPES.items():
            assert issubclass(cls, BaseModel), f"{name} is not a Pydantic BaseModel"

    def test_edge_types_registered(self):
        assert len(EDGE_TYPES) == 9
        expected_edges = {
            "Supersedes", "DerivedFrom", "Validates", "Contradicts",
            "TestedBy", "References", "Blocks", "EmergedFrom", "AppliesTo",
        }
        assert set(EDGE_TYPES.keys()) == expected_edges


class TestReservedFieldNames:
    @pytest.mark.parametrize("entity_name,entity_cls", list(ENTITY_TYPES.items()))
    def test_no_reserved_fields(self, entity_name, entity_cls):
        field_names = set(entity_cls.model_fields.keys())
        conflicts = field_names & GRAPHITI_RESERVED
        assert not conflicts, (
            f"{entity_name} uses reserved Graphiti field(s): {conflicts}. "
            f"Rename to avoid collisions."
        )


class TestDevSession:
    def test_create_valid(self):
        session = DevSession(
            session_date=datetime(2026, 4, 24),
            session_summary="Implemented the caching layer",
            focus_area="backend",
            outcome_status="productive",
            participants=["Developer", "Claude-Opus-4"],
        )
        assert session.outcome_status == "productive"
        assert len(session.participants) == 2

    def test_outcome_status_enum(self):
        for status in ["productive", "blocked", "exploratory", "pivoted"]:
            s = DevSession(
                session_date=datetime.now(),
                session_summary="test",
                focus_area="test",
                outcome_status=status,
            )
            assert s.outcome_status == status


class TestDecision:
    def test_create_valid(self):
        d = Decision(
            decision_text="Use PostgreSQL for the user store",
            rationale="Better JSON support than MySQL",
            status="active",
            decided_at=datetime(2026, 4, 24),
            domain="data_model",
        )
        assert d.status == "active"
        assert d.domain == "data_model"

    def test_all_domains(self):
        domains = [
            "architecture", "extraction_pipeline", "frontend", "data_model",
            "infrastructure", "product", "sales", "compliance", "tooling",
        ]
        for domain in domains:
            d = Decision(
                decision_text="test",
                rationale="test",
                status="active",
                decided_at=datetime.now(),
                domain=domain,
            )
            assert d.domain == domain


class TestArtifact:
    def test_create_minimal(self):
        a = Artifact(
            artifact_type="commit",
            title="Fix dedup logic",
            artifact_created_at=datetime.now(),
        )
        assert a.path is None
        assert a.repo is None

    def test_create_full(self):
        a = Artifact(
            artifact_type="spec",
            title="Caching Strategy Spec",
            path="docs/specs/CACHING.md",
            repo="my-project",
            commit_sha="abc123",
            artifact_created_at=datetime(2026, 4, 24),
        )
        assert a.repo == "my-project"


class TestProblem:
    def test_open_problem(self):
        p = Problem(
            description="API returns 500 on concurrent requests",
            status="investigating",
            severity="high",
            first_observed=datetime(2026, 4, 9),
        )
        assert p.resolved_at is None

    def test_resolved_problem(self):
        p = Problem(
            description="Memory leak in worker process",
            status="resolved",
            severity="critical",
            first_observed=datetime(2026, 4, 10),
            resolved_at=datetime(2026, 4, 16),
        )
        assert p.resolved_at is not None


class TestExperiment:
    def test_successful_experiment(self):
        e = Experiment(
            hypothesis="Adding Redis cache will reduce p99 latency below 200ms",
            approach="Added Redis caching layer to the hot path",
            outcome="p99 dropped from 450ms to 120ms",
            success=True,
            metrics={"p99_before_ms": 450, "p99_after_ms": 120},
            run_at=datetime(2026, 4, 16),
        )
        assert e.success is True
        assert e.metrics["p99_after_ms"] == 120

    def test_failed_experiment(self):
        e = Experiment(
            hypothesis="Batch processing will reduce API costs by 50%",
            approach="Batched requests in groups of 100",
            outcome="Timeout errors increased, no cost reduction",
            success=False,
            run_at=datetime(2026, 4, 18),
        )
        assert e.success is False


class TestConcept:
    def test_create_concept(self):
        c = Concept(
            concept_name="Circuit Breaker",
            definition="Pattern to detect failures and prevent cascading errors across services",
            first_introduced=datetime(2026, 2, 15),
        )
        # 'name' field is NOT used (reserved by Graphiti)
        assert c.concept_name == "Circuit Breaker"
        assert "name" not in Concept.model_fields

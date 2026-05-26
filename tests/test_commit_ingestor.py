"""
Tests for the commit ingestor.

Tests episode body construction and keyword detection
WITHOUT requiring a live Graphiti or git connection.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.commit_ingestor import _build_extraction_instructions, _KEYWORD_PATTERNS


class TestKeywordDetection:
    def test_decision_keyword(self):
        msg = "Decision: Use Redis for session caching\n\nRationale: low latency"
        instructions = _build_extraction_instructions(msg)
        assert instructions is not None
        assert "Decision entity" in instructions

    def test_fix_keyword(self):
        msg = "Fix: Race condition in worker pool\n\nAdded mutex lock"
        instructions = _build_extraction_instructions(msg)
        assert instructions is not None
        assert "Problem entity" in instructions
        assert "Decision entity" in instructions

    def test_experiment_keyword(self):
        msg = "Experiment: Batch processing for API calls\n\nHypothesis: ..."
        instructions = _build_extraction_instructions(msg)
        assert instructions is not None
        assert "Experiment entity" in instructions

    def test_refs_keyword(self):
        msg = "Add caching layer\n\nRefs: docs/specs/CACHING_STRATEGY.md"
        instructions = _build_extraction_instructions(msg)
        assert instructions is not None
        assert "References edge" in instructions

    def test_no_keywords(self):
        msg = "chore: update requirements.txt"
        instructions = _build_extraction_instructions(msg)
        assert instructions is None

    def test_multiple_keywords(self):
        msg = "Fix: broken dedup\nDecision: revert to previous approach"
        instructions = _build_extraction_instructions(msg)
        assert "Problem entity" in instructions
        assert "Decision entity" in instructions

    def test_case_insensitive(self):
        msg = "decision: lowercase works too"
        instructions = _build_extraction_instructions(msg)
        assert instructions is not None


class TestKeywordPatterns:
    def test_all_patterns_compile(self):
        for name, pattern in _KEYWORD_PATTERNS.items():
            assert pattern is not None, f"Pattern '{name}' is None"
            # Verify it's a compiled regex
            assert hasattr(pattern, "search"), f"Pattern '{name}' is not compiled"

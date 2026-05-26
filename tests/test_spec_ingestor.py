"""
Tests for the spec ingestor.

Tests file classification, date extraction, and hash tracking
WITHOUT requiring a live Graphiti connection.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.spec_ingestor import _classify_source, _extract_reference_time


class TestFileClassification:
    def test_architecture_dir(self):
        assert _classify_source(Path("docs/architecture/ADR-001-foo.md")) == "adr"

    def test_adr_in_name(self):
        assert _classify_source(Path("docs/ADR-002-bar.md")) == "adr"

    def test_session_dir(self):
        assert _classify_source(Path("docs/sessions/SESSION_SUMMARY_2026-04-24.md")) == "session_summary"

    def test_sprint_dir(self):
        assert _classify_source(Path("docs/sprints/CACHING_SPEC.md")) == "spec"

    def test_generic_spec(self):
        assert _classify_source(Path("docs/future_features/ROADMAP.md")) == "spec"


class TestDateExtraction:
    def test_date_from_filename(self, tmp_path):
        f = tmp_path / "SPRINT_2026-04-01.md"
        f.write_text("# Sprint spec\nNo frontmatter.", encoding="utf-8")
        dt = _extract_reference_time(f, f.read_text())
        assert dt.year == 2026
        assert dt.month == 4
        assert dt.day == 1

    def test_date_from_frontmatter(self, tmp_path):
        content = "---\ndate: 2026-03-15\n---\n# Spec"
        f = tmp_path / "some_spec.md"
        f.write_text(content, encoding="utf-8")
        dt = _extract_reference_time(f, content)
        assert dt.year == 2026
        assert dt.month == 3

    def test_date_from_session_date_frontmatter(self, tmp_path):
        content = "---\nsession_date: 2026-04-24\n---\n# Session"
        f = tmp_path / "session.md"
        f.write_text(content, encoding="utf-8")
        dt = _extract_reference_time(f, content)
        assert dt.month == 4
        assert dt.day == 24

    def test_fallback_to_mtime(self, tmp_path):
        f = tmp_path / "no_date_anywhere.md"
        f.write_text("# No date info", encoding="utf-8")
        dt = _extract_reference_time(f, f.read_text())
        # Should be close to now (file just created)
        assert (datetime.now() - dt).total_seconds() < 60

    def test_date_prefix_filename(self, tmp_path):
        f = tmp_path / "2026-03-22_caching_strategy.md"
        f.write_text("# Caching Strategy", encoding="utf-8")
        dt = _extract_reference_time(f, f.read_text())
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 22


class TestSettingsValidation:
    def test_database_isolation_allows_neo4j_default(self):
        """'neo4j' (Aura default) is allowed — isolation via group_id instead."""
        from config.settings import BrainSettings as _BrainSettings

        s = _BrainSettings(NEO4J_DATABASE="neo4j")
        assert s.NEO4J_DATABASE == "neo4j"
        assert s.GRAPHITI_GROUP_ID == "dev_brain"

    def test_database_isolation_rejects_blocked_names(self):
        from config.settings import BrainSettings as _BrainSettings

        with pytest.raises(ValueError, match="FATAL"):
            _BrainSettings(NEO4J_DATABASE="production", BLOCKED_DB_NAMES="production,prod_db")

    def test_database_isolation_accepts_brain(self):
        from config.settings import BrainSettings as _BrainSettings

        s = _BrainSettings(NEO4J_DATABASE="dev_brain")
        assert s.NEO4J_DATABASE == "dev_brain"

    def test_group_id_default(self):
        """GRAPHITI_GROUP_ID defaults to 'dev_brain' for data isolation."""
        from config.settings import BrainSettings as _BrainSettings

        s = _BrainSettings()
        assert s.GRAPHITI_GROUP_ID == "dev_brain"

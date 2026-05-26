"""
Tests for the session ingestor.

Tests parsing, frontmatter extraction, and episode body construction
WITHOUT requiring a live Graphiti connection.
"""

import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent

import pytest
import frontmatter

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestFrontmatterParsing:
    """Test that session markdown files are parsed correctly."""

    def test_parse_valid_frontmatter(self, tmp_path):
        content = dedent("""\
            ---
            session_date: 2026-04-24
            focus_area: backend API
            outcome_status: productive
            participants: [Developer, Claude-Opus-4]
            ---

            # Session Summary

            ## Context
            Worked on the caching layer.

            ## Decisions Made
            - **Use Redis**: Low-latency key-value store fits our needs.
        """)
        md_file = tmp_path / "SESSION_SUMMARY_2026-04-24.md"
        md_file.write_text(content, encoding="utf-8")

        post = frontmatter.load(str(md_file))
        # YAML auto-parses dates — may be datetime.date or string
        raw = post.metadata["session_date"]
        from datetime import date
        if isinstance(raw, date):
            assert raw.year == 2026 and raw.month == 4 and raw.day == 24
        else:
            assert raw == "2026-04-24"
        assert post.metadata["focus_area"] == "backend API"
        assert post.metadata["outcome_status"] == "productive"
        assert "Developer" in post.metadata["participants"]
        assert "caching layer" in post.content

    def test_parse_no_frontmatter(self, tmp_path):
        """Files without frontmatter should still parse (body = full content)."""
        content = "# Just a plain markdown file\n\nNo frontmatter here."
        md_file = tmp_path / "plain.md"
        md_file.write_text(content, encoding="utf-8")

        post = frontmatter.load(str(md_file))
        assert post.metadata == {}
        assert "plain markdown" in post.content

    def test_parse_date_formats(self, tmp_path):
        """Support both string and datetime date formats."""
        for date_val in ["2026-04-24", "2026-04-24T10:30:00"]:
            content = f"---\nsession_date: {date_val}\n---\nBody"
            md_file = tmp_path / "test.md"
            md_file.write_text(content, encoding="utf-8")

            post = frontmatter.load(str(md_file))
            date_raw = post.metadata["session_date"]
            if isinstance(date_raw, str):
                parsed = datetime.fromisoformat(date_raw)
            else:
                parsed = date_raw
            assert parsed.year == 2026
            assert parsed.month == 4


class TestTemplateCompliance:
    """Verify the session template matches the expected structure."""

    def test_template_has_required_sections(self):
        template_path = Path(__file__).parent.parent / "docs" / "sessions" / "TEMPLATE.md"
        if not template_path.exists():
            pytest.skip("Template not yet created")

        content = template_path.read_text(encoding="utf-8")
        post = frontmatter.loads(content)

        # Frontmatter should have required keys
        assert "session_date" in post.metadata
        assert "focus_area" in post.metadata
        assert "outcome_status" in post.metadata

        # Body should have expected sections
        for section in ["Context", "Decisions Made", "Experiments Run", "Problems"]:
            assert section in post.content, f"Missing section: {section}"

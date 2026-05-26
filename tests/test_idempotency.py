"""
Tests for the idempotency layer.

Critical for safety — the git hook depends on this to prevent
duplicate ingestion loops from burning LLM budget.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.idempotency import (
    content_hash,
    is_already_ingested,
    mark_ingested,
    get_ingested_count,
    clear_hashes,
    _HASH_FILE,
    _STATE_DIR,
)


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    """Use a temporary state directory for each test."""
    import ingestion.idempotency as mod

    test_state_dir = tmp_path / "state"
    test_state_dir.mkdir()
    test_hash_file = test_state_dir / "ingested_hashes.json"

    monkeypatch.setattr(mod, "_STATE_DIR", test_state_dir)
    monkeypatch.setattr(mod, "_HASH_FILE", test_hash_file)
    yield


class TestContentHash:
    def test_deterministic(self):
        h1 = content_hash("test content")
        h2 = content_hash("test content")
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = content_hash("content A")
        h2 = content_hash("content B")
        assert h1 != h2

    def test_sha256_format(self):
        h = content_hash("test")
        assert len(h) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in h)


class TestIdempotency:
    def test_not_ingested_initially(self):
        assert not is_already_ingested("new content")

    def test_mark_then_check(self):
        content = "session summary about caching strategy"
        assert not is_already_ingested(content)
        mark_ingested(content)
        assert is_already_ingested(content)

    def test_different_content_not_blocked(self):
        mark_ingested("content A")
        assert not is_already_ingested("content B")

    def test_count_tracks_ingestions(self):
        assert get_ingested_count() == 0
        mark_ingested("episode 1")
        mark_ingested("episode 2")
        mark_ingested("episode 3")
        assert get_ingested_count() == 3

    def test_duplicate_mark_no_increment(self):
        mark_ingested("same content")
        mark_ingested("same content")
        assert get_ingested_count() == 1

    def test_clear_hashes(self):
        mark_ingested("content 1")
        mark_ingested("content 2")
        assert get_ingested_count() == 2
        clear_hashes()
        assert get_ingested_count() == 0
        assert not is_already_ingested("content 1")


class TestIdempotencyPersistence:
    def test_survives_reload(self):
        """Hash store persists across function calls (simulates process restart)."""
        mark_ingested("persistent content")
        # Clear in-memory state by re-reading from disk
        assert is_already_ingested("persistent content")

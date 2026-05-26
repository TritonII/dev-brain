"""
Tests for the GitHub Ingestor
=============================

Validates issue/PR episode body construction and API formatting logic
without calling live GitHub or Graphiti endpoints.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.github_ingestor import (
    _build_issue_episode,
    _build_pr_episode,
    GitHubClient,
)


class TestEpisodeBuilders:
    """Test that issue and PR dicts map to formatted markdown text correctly."""

    def test_build_issue_episode(self):
        sample_issue = {
            "number": 42,
            "title": "Fix concurrent memory leak",
            "state": "closed",
            "user": {"login": "sturgdev"},
            "created_at": "2026-05-10T12:00:00Z",
            "closed_at": "2026-05-12T15:30:00Z",
            "body": "There is a memory leak in concurrent worker routines."
        }

        episode = _build_issue_episode(sample_issue)
        
        assert "GitHub Issue #42: Fix concurrent memory leak" in episode
        assert "State: closed" in episode
        assert "Author: sturgdev" in episode
        assert "Created At: 2026-05-10T12:00:00Z" in episode
        assert "Closed At: 2026-05-12T15:30:00Z" in episode
        assert "Description:\nThere is a memory leak" in episode

    def test_build_pr_episode(self):
        sample_pr = {
            "number": 101,
            "title": "Implement auth middleware",
            "state": "closed",
            "user": {"login": "alexfounder"},
            "created_at": "2026-05-20T10:00:00Z",
            "merged_at": "2026-05-21T09:00:00Z",
            "merged": True,
            "body": "Implements OAuth2 flows."
        }

        episode = _build_pr_episode(sample_pr)
        
        assert "GitHub Pull Request #101: Implement auth middleware" in episode
        assert "State: closed" in episode
        assert "Merged: True" in episode
        assert "Author: alexfounder" in episode
        assert "Description:\nImplements OAuth2 flows." in episode


class TestGitHubClient:
    """Test standard client setups and endpoint path constructions."""

    def test_client_headers_without_token(self):
        client = GitHubClient(token=None)
        assert "Authorization" not in client.headers
        assert client.headers["Accept"] == "application/vnd.github+json"

    def test_client_headers_with_token(self):
        client = GitHubClient(token="ghp_test123")
        assert client.headers["Authorization"] == "Bearer ghp_test123"
        assert client.headers["Accept"] == "application/vnd.github+json"

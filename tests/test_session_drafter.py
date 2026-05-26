"""
Tests for the AI Session Summary Drafter
=========================================

Validates git history extraction and LLM-based session note drafting.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.session_drafter import _get_git_history, draft_session_summary


class TestSessionDrafter:
    """Test git compilation and LLM generation logic."""

    @patch("ingestion.session_drafter.Repo")
    def test_get_git_history_empty(self, mock_repo_cls):
        # Setup mocked repo with no commits
        mock_repo = MagicMock()
        mock_repo.bare = False
        mock_repo.iter_commits.return_value = []
        mock_repo_cls.return_value = mock_repo

        history = _get_git_history(Path("."))
        assert "No recent commits found" in history

    @patch("ingestion.session_drafter.Repo")
    def test_get_git_history_with_commits(self, mock_repo_cls):
        # Setup mock commit
        mock_commit = MagicMock()
        mock_commit.hexsha = "abcdef1234567890"
        mock_commit.author.name = "Test Author"
        mock_commit.committed_datetime.isoformat.return_value = "2026-05-26T12:00:00Z"
        mock_commit.message = "feat: Add new awesome feature"
        mock_commit.parents = []
        
        mock_item = MagicMock()
        mock_item.path = "src/main.py"
        mock_commit.tree.traverse.return_value = [mock_item]

        mock_repo = MagicMock()
        mock_repo.bare = False
        mock_repo.iter_commits.return_value = [mock_commit]
        mock_repo_cls.return_value = mock_repo

        history = _get_git_history(Path("."))
        assert "Commit #1: abcdef12" in history
        assert "Author: Test Author" in history
        assert "Message: feat: Add new awesome feature" in history
        assert "Files changed: src/main.py" in history

    @pytest.mark.asyncio
    @patch("ingestion.session_drafter._get_git_history")
    @patch("ingestion.session_drafter.get_graphiti")
    async def test_draft_session_summary_success(self, mock_get_graphiti, mock_get_git_history):
        # Mock git history
        mock_get_git_history.return_value = "Commit #1: message"
        
        # Mock LLM and Graphiti
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """
        {
            "title": "Optimized Caching",
            "content": "## Context\\nOptimized Cache tier."
        }
        """
        
        mock_graphiti = AsyncMock()
        mock_graphiti.llm_client = mock_llm
        mock_get_graphiti.return_value = mock_graphiti

        title, content = await draft_session_summary(Path("."))
        assert title == "Optimized Caching"
        assert "Optimized Cache tier." in content

    @pytest.mark.asyncio
    @patch("ingestion.session_drafter._get_git_history")
    @patch("ingestion.session_drafter.get_graphiti")
    async def test_draft_session_summary_llm_failure_fallback(self, mock_get_graphiti, mock_get_git_history):
        # Mock git history
        mock_get_git_history.return_value = "Commit #1: message"
        
        # Mock LLM error
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = Exception("API quota exceeded")
        
        mock_graphiti = AsyncMock()
        mock_graphiti.llm_client = mock_llm
        mock_get_graphiti.return_value = mock_graphiti

        title, content = await draft_session_summary(Path("."))
        assert title == "Recent Development Sprint"
        assert "Recent git commits analyzed:" in content
        assert "Commit #1: message" in content

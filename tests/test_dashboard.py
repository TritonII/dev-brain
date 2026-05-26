"""
Tests for the Web Dashboard Server
==================================

Validates FastAPI endpoints and response formats under mocked database
and Graphiti clients (no live Neo4j required).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import FastAPI app
with patch("config.graphiti_init.get_graphiti", new_callable=AsyncMock):
    from dashboard.server import app

client = TestClient(app)


class TestDashboardEndpoints:
    """Test standard API response shapes and model validations."""

    @patch("dashboard.server.get_graphiti")
    def test_health_endpoint_healthy(self, mock_get_graphiti):
        # Mock Graphiti and driver health check
        mock_graphiti = AsyncMock()
        mock_get_graphiti.return_value = mock_graphiti
        
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "connected"}
        mock_graphiti.graph_driver.health_check.assert_called_once()

    @patch("dashboard.server.get_graphiti")
    def test_health_endpoint_unhealthy(self, mock_get_graphiti):
        # Mock health check exception
        mock_graphiti = AsyncMock()
        mock_graphiti.graph_driver.health_check.side_effect = Exception("Neo4j offline")
        mock_get_graphiti.return_value = mock_graphiti
        
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "error"
        assert "Neo4j offline" in response.json()["message"]

    @patch("dashboard.server.execute_cypher")
    def test_graph_endpoint_empty(self, mock_execute_cypher):
        # Mock empty database records
        mock_execute_cypher.return_value = []
        
        response = client.get("/api/graph")
        assert response.status_code == 200
        data = response.json()
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_ingest_endpoint_validation_error(self):
        # Test validation error (empty body payload)
        response = client.post("/api/ingest", json={})
        assert response.status_code == 422  # Unprocessable Entity
        
        # Test validation error (missing content)
        response = client.post("/api/ingest", json={"title": "Sprint 3"})
        assert response.status_code == 422

    @patch("dashboard.server.get_settings")
    @patch("dashboard.server.get_graphiti")
    def test_ingest_endpoint_read_only(self, mock_get_graphiti, mock_get_settings):
        # Mock read-only setting
        mock_settings = AsyncMock()
        mock_settings.GRAPHITI_READ_ONLY = True
        mock_get_settings.return_value = mock_settings
        
        response = client.post("/api/ingest", json={"title": "Sprint 3", "content": "Done"})
        assert response.status_code == 400
        assert "read-only mode" in response.json()["detail"]

    @patch("dashboard.server.IS_DEMO_MODE", new=True)
    def test_story_log_endpoint_demo_mode(self):
        response = client.get("/api/story_log")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["title"] == "Sprint 1: Caching Tier"
        assert len(data[0]["decisions"]) == 1
        assert data[0]["decisions"][0]["name"] == "Use Redis for Cache"

    @patch("dashboard.server.IS_DEMO_MODE", new=False)
    @patch("dashboard.server.execute_cypher")
    def test_story_log_endpoint_db_mode(self, mock_execute_cypher):
        mock_session_node = MagicMock()
        mock_session_node.get.side_effect = lambda key, default=None: {
            "uuid": "session_123",
            "name": "Live Sprint Session",
            "summary": "Live testing summary",
            "created_at": "2026-05-26T12:00:00Z",
            "session_date": "2026-05-26"
        }.get(key, default)
        
        mock_session_record = MagicMock()
        mock_session_record.get.return_value = mock_session_node
        
        # Connection records
        mock_decision_node = MagicMock()
        mock_decision_node.labels = ["Decision"]
        mock_decision_node.get.side_effect = lambda key, default=None: {
            "uuid": "dec_1",
            "name": "Live Choice",
            "summary": "Live rationale choice",
            "attributes": '{"status": "active", "rationale": "fast"}'
        }.get(key, default)
        
        mock_conn_record = MagicMock()
        mock_conn_record.get.return_value = mock_decision_node
        
        # Configure side effect for execute_cypher:
        # First call: query sessions -> returns mock_session_record
        # Second call: query connections -> returns mock_conn_record
        mock_execute_cypher.side_effect = [
            [mock_session_record],
            [mock_conn_record]
        ]
        
        response = client.get("/api/story_log")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Live Sprint Session"
        assert len(data[0]["decisions"]) == 1
        assert data[0]["decisions"][0]["name"] == "Live Choice"

    @patch("dashboard.server.IS_DEMO_MODE", new=True)
    def test_draft_session_endpoint_demo_mode(self):
        response = client.get("/api/draft_session")
        assert response.status_code == 200
        data = response.json()
        assert "title" in data
        assert "content" in data
        assert "Sprint 4:" in data["title"]

    @patch("dashboard.server.IS_DEMO_MODE", new=False)
    @patch("ingestion.session_drafter.draft_session_summary", new_callable=AsyncMock)
    def test_draft_session_endpoint_db_mode(self, mock_draft_summary):
        mock_draft_summary.return_value = ("Live Sprint Draft", "## Detailed Context")
        
        response = client.get("/api/draft_session")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Live Sprint Draft"
        assert data["content"] == "## Detailed Context"


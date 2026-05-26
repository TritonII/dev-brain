"""
Tests for the Web Dashboard Server
==================================

Validates FastAPI endpoints and response formats under mocked database
and Graphiti clients (no live Neo4j required).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

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

"""Integration tests for Web API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from simanalysis.web.api import app


class TestWebApi:
    """Test Web API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def sample_mods_path(self):
        """Get path to sample mods fixture."""
        return Path(__file__).parent.parent / "fixtures" / "sample_mods"

    def test_root(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_scan_directory(self, client, sample_mods_path):
        """Test scan endpoint."""
        response = client.post(
            "/api/scan",
            json={
                "path": str(sample_mods_path),
                "recursive": True,
                "quick": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "summary" in data
        assert "conflicts" in data
        assert "performance" in data
        assert "recommendations" in data
        
        # Check content
        assert data["summary"]["total_mods"] == 5
        assert len(data["conflicts"]) > 0
        assert data["performance"]["total_size_mb"] >= 0

    def test_scan_invalid_directory(self, client):
        """Test scan with invalid directory."""
        response = client.post(
            "/api/scan",
            json={
                "path": "/path/to/nonexistent/directory",
                "recursive": True
            }
        )
        
        assert response.status_code == 400
        assert "Invalid directory" in response.json()["detail"]

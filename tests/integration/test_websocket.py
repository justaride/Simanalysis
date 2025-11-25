"""Integration tests for WebSocket API."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from simanalysis.web.api import app

class TestWebSocket:
    """Test WebSocket endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def sample_mods_path(self):
        """Get path to sample mods fixture."""
        return Path(__file__).parent.parent / "fixtures" / "sample_mods"

    def test_websocket_scan(self, client, sample_mods_path):
        """Test scanning via WebSocket."""
        with client.websocket_connect("/api/ws/scan") as websocket:
            # Send configuration
            websocket.send_json({
                "path": str(sample_mods_path),
                "recursive": True,
                "quick": True
            })
            
            # Receive messages
            messages = []
            while True:
                data = websocket.receive_json()
                messages.append(data)
                
                if data["status"] in ("complete", "error"):
                    break
            
            # Verify sequence
            assert len(messages) > 0
            
            # Check for progress updates
            progress_updates = [m for m in messages if m["status"] == "scanning"]
            assert len(progress_updates) > 0
            
            # Check first update structure
            first = progress_updates[0]
            assert "current" in first
            assert "total" in first
            assert "file" in first
            
            # Check completion
            last = messages[-1]
            assert last["status"] == "complete"
            assert "result" in last
            assert "summary" in last["result"]

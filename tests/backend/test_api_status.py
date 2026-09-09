from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import httpx

from backend.main import app

client = TestClient(app)

def test_get_status_online():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "lm_studio_endpoint" in data
    assert "default_llm_model" in data
    assert "default_embedding_model" in data
    assert isinstance(data["lm_studio_connected"], bool)

@patch("httpx.AsyncClient.get")
def test_get_status_lm_studio_connected(mock_get):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["lm_studio_connected"] is True

@patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused"))
def test_get_status_lm_studio_disconnected(mock_get):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["lm_studio_connected"] is False
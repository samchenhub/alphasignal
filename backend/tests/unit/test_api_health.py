"""
Unit tests for API endpoints.
Startup events (ingestion, price sync) are mocked to avoid DB/network calls.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """FastAPI TestClient with startup side-effects mocked out."""
    with patch("app.scheduler.tasks.run_ingestion", new_callable=AsyncMock), \
         patch("app.scheduler.tasks.run_price_sync", new_callable=AsyncMock), \
         patch("app.main.run_ingestion", new_callable=AsyncMock), \
         patch("app.main.run_price_sync", new_callable=AsyncMock):
        from app.main import app
        with TestClient(app) as c:
            yield c


class TestHealthEndpoint:
    def test_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_correct_body(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_api_docs_accessible(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema_accessible(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "AlphaSignal"

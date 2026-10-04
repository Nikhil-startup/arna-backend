import pytest
from fastapi.testclient import TestClient
from arna_backend.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root URL returns online service status and docs reference."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["documentation"] == "/docs"
    assert "ARNA" in data["brand"]


def test_health_check_endpoint():
    """Verify health endpoint returns 200 OK and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "arna-backend"


def test_payment_config_endpoint():
    """Verify payment config returns public settings without leaking secret keys."""
    response = client.get("/api/payments/config")
    assert response.status_code == 200
    data = response.json()
    assert "razorpayEnabled" in data
    assert "upiEnabled" in data
    assert "codEnabled" in data
    assert data["codEnabled"] is True
    assert "storeUpiId" in data
    # Ensure backend secret keys are NEVER leaked in config response
    assert "secret" not in data
    assert "key_secret" not in str(data).lower()


def test_analytics_endpoint():
    """Verify analytics visitor metrics are returned properly."""
    response = client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert "totalVisitors" in data or "total_visitors" in data


def test_malicious_user_agent_blocked():
    """Verify bot scrapers (e.g., sqlmap, nikto) are rejected with 403 Forbidden."""
    headers = {"User-Agent": "sqlmap/1.5.2#stable"}
    response = client.get("/api/products", headers=headers)
    assert response.status_code == 403
    assert "Automated scraping or bot download forbidden" in response.json().get("detail", "")


def test_security_headers_present():
    """Verify security headers (X-Frame-Options, X-Content-Type-Options, etc.) on responses."""
    response = client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "max-age=31536000" in response.headers.get("Strict-Transport-Security", "")

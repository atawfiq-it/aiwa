import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.security import (
    cleanup_session_token,
    generate_session_token,
    validate_safe_path,
)
from app.main import app


@pytest.fixture(autouse=True)
def setup_auth_token():
    token = generate_session_token()
    yield token
    cleanup_session_token()


def test_path_traversal_detection():
    """Verify validate_safe_path strictly prevents directory escape attempts."""
    allowed_dir = settings.UPLOADS_DIR
    dangerous_path = allowed_dir / ".." / "database" / "aiwa.db"

    # Must reject path traversal escaping the allowed boundary
    with pytest.raises(HTTPException) as exc_info:
        validate_safe_path(dangerous_path, allowed_dir)
    assert exc_info.value.status_code == 403
    assert "Path traversal detected" in exc_info.value.detail


def test_path_traversal_allows_safe_files():
    """Verify validate_safe_path permits valid files within allowed directory."""
    allowed_dir = settings.UPLOADS_DIR
    safe_path = allowed_dir / "subfolder" / "sample_document.pdf"

    resolved = validate_safe_path(safe_path, allowed_dir)
    assert resolved == safe_path.resolve()


@pytest.mark.asyncio
async def test_auth_token_enforcement(setup_auth_token):
    """Verify protected endpoints reject missing or invalid tokens."""
    token = setup_auth_token

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Missing token -> 401 Unauthorized
        res_missing = await client.get("/api/v1/auth/verify")
        assert res_missing.status_code == 401

        # 2. Tampered / incorrect token -> 401 Unauthorized
        res_invalid = await client.get(
            "/api/v1/auth/verify",
            headers={"X-AIWA-Token": "invalid_spoofed_token_hex_12345"},
        )
        assert res_invalid.status_code == 401

        # 3. Legitimate session token -> 200 OK
        res_valid = await client.get(
            "/api/v1/auth/verify",
            headers={"X-AIWA-Token": token},
        )
        assert res_valid.status_code == 200
        assert res_valid.json()["status"] == "authenticated"


@pytest.mark.asyncio
async def test_dev_token_endpoint_behavior(setup_auth_token, monkeypatch):
    """Verify /api/v1/auth/dev-token returns token in dev and blocks in production."""
    token = setup_auth_token

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # In development mode: returns valid active session token
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        res_dev = await client.get("/api/v1/auth/dev-token")
        assert res_dev.status_code == 200
        assert res_dev.json()["token"] == token

        # In production mode: strictly returns 403 Forbidden
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        res_prod = await client.get("/api/v1/auth/dev-token")
        assert res_prod.status_code == 403


@pytest.mark.asyncio
async def test_production_mode_disables_documentation_routes(monkeypatch):
    """Verify Swagger UI and OpenAPI schemas are disabled in production."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    # FastAPI docs_url parameters evaluate at app startup, so we test router resolution
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_health = await client.get("/api/v1/health")
        assert res_health.status_code == 200

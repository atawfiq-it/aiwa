import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import cleanup_session_token, generate_session_token
from app.main import app


@pytest.fixture(autouse=True)
def setup_token():
    token = generate_session_token()
    yield token
    cleanup_session_token()


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_auth_protection(setup_token):
    token = setup_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request without token -> 401
        res_unauth = await client.get("/api/v1/auth/verify")
        assert res_unauth.status_code == 401

        # Request with valid token -> 200
        res_auth = await client.get(
            "/api/v1/auth/verify",
            headers={"X-AIWA-Token": token},
        )
        assert res_auth.status_code == 200
        assert res_auth.json()["status"] == "authenticated"

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import cleanup_session_token, generate_session_token
from app.main import app
from app.supervisors.model_supervisor import ModelState
from app.supervisors.vram_arbiter import vram_arbiter


@pytest.fixture(autouse=True)
def setup_auth():
    token = generate_session_token()
    yield token
    cleanup_session_token()


def test_vram_arbiter_status():
    status = vram_arbiter.get_vram_status()
    assert "total_mb" in status
    assert "free_mb" in status
    assert status["total_mb"] > 0


@pytest.mark.asyncio
async def test_supervisor_status_endpoint(setup_auth):
    token = setup_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/models/status",
            headers={"X-AIWA-Token": token},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == ModelState.UNLOADED.value
    assert "vram" in data


@pytest.mark.asyncio
async def test_chat_without_loaded_model(setup_auth):
    token = setup_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers={"X-AIWA-Token": token},
        )
    assert res.status_code == 200
    # Stream returns error event because no model is loaded
    assert "event: error" in res.text

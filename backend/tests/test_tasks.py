import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import cleanup_session_token, generate_session_token
from app.main import app


@pytest.fixture(autouse=True)
def setup_auth():
    token = generate_session_token()
    yield token
    cleanup_session_token()


@pytest.mark.asyncio
async def test_task_queue_and_comfyui_status(setup_auth):
    token = setup_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-AIWA-Token": token}

        # 1. Check ComfyUI service status endpoint (safe even when ComfyUI is offline)
        status_res = await client.get("/api/v1/media/comfyui/status", headers=headers)
        assert status_res.status_code == 200
        assert "available" in status_res.json()

        # 2. Submit image generation task
        gen_res = await client.post(
            "/api/v1/media/images/generate",
            json={"prompt": "a cinematic digital painting of a cybernetic owl"},
            headers=headers,
        )
        assert gen_res.status_code == 200
        task_data = gen_res.json()
        assert task_data["task_type"] == "image_generation"
        assert task_data["status"] == "queued"
        task_id = task_data["id"]

        # 3. Retrieve task
        task_res = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        assert task_res.status_code == 200
        assert task_res.json()["id"] == task_id

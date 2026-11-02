import io

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
async def test_conversation_lifecycle(setup_auth):
    token = setup_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-AIWA-Token": token}

        # 1. Create conversation
        create_res = await client.post(
            "/api/v1/conversations",
            json={"title": "Test AI Chat"},
            headers=headers,
        )
        assert create_res.status_code == 200
        conv_id = create_res.json()["id"]

        # 2. Add user message
        msg_res = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": "What is AIWA?"},
            headers=headers,
        )
        assert msg_res.status_code == 200
        assert msg_res.json()["role"] == "user"

        # 3. Retrieve conversation
        get_res = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
        assert get_res.status_code == 200
        data = get_res.json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "What is AIWA?"

        # 4. Delete conversation
        del_res = await client.delete(f"/api/v1/conversations/{conv_id}", headers=headers)
        assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_file_upload(setup_auth):
    token = setup_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-AIWA-Token": token}

        file_payload = io.BytesIO(b"dummy pdf file content")
        files = {"file": ("test_doc.pdf", file_payload, "application/pdf")}

        res = await client.post("/api/v1/files/upload", files=files, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["file_name"] == "test_doc.pdf"
        assert data["mime_type"] == "application/pdf"

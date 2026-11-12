import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import cleanup_session_token, generate_session_token
from app.main import app
from app.services.embeddings.rag_service import rag_service


@pytest.fixture(autouse=True)
def setup_auth():
    token = generate_session_token()
    yield token
    cleanup_session_token()


def test_markdown_chunking():
    sample_md = "# Heading 1\nContent paragraph 1\n\n## Subheading\nContent paragraph 2"
    chunks = rag_service.chunk_markdown(sample_md)
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_knowledge_base_endpoints(setup_auth):
    token = setup_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-AIWA-Token": token}

        # 1. Create KB
        res = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Engineering Docs", "description": "System architecture"},
            headers=headers,
        )
        assert res.status_code == 200
        kb_id = res.json()["id"]

        # 2. List KBs
        list_res = await client.get("/api/v1/knowledge-bases", headers=headers)
        assert list_res.status_code == 200
        assert any(k["id"] == kb_id for k in list_res.json())

        # 3. Check audio status
        audio_res = await client.get("/api/v1/media/audio/status", headers=headers)
        assert audio_res.status_code == 200

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
async def test_workflow_definition_and_trigger(setup_auth):
    token = setup_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-AIWA-Token": token}

        # 1. Register "Document to Audio Briefing" Workflow Template
        wf_payload = {
            "name": "Document to Audio Briefing",
            "description": "Extracts PDF, generates executive summary, converts to speech audio.",
            "steps": [
                {"task_type": "pdf_extraction"},
                {"task_type": "llm_summarize"},
                {"task_type": "text_to_speech"},
            ],
        }
        create_res = await client.post("/api/v1/workflows", json=wf_payload, headers=headers)
        assert create_res.status_code == 200
        wf_id = create_res.json()["id"]

        # 2. Trigger workflow run
        run_res = await client.post(
            f"/api/v1/workflows/{wf_id}/run",
            json={"input_data": {"attachment_id": "dummy_id"}},
            headers=headers,
        )
        assert run_res.status_code == 200
        run_data = run_res.json()
        assert run_data["status"] == "running"
        assert run_data["total_steps"] == 3
        assert run_data["current_step_index"] == 0

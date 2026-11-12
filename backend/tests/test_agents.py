import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import cleanup_session_token, generate_session_token
from app.main import app
from app.services.agents.sandbox import python_sandbox


@pytest.fixture(autouse=True)
def setup_auth():
    token = generate_session_token()
    yield token
    cleanup_session_token()


def test_python_sandbox_execution():
    code = "result = 6 * 7\nprint(f'Computed: {result}')"
    outcome = python_sandbox.execute(code)
    assert outcome["status"] == "success"
    assert "Computed: 42" in outcome["stdout"]


def test_python_sandbox_timeout():
    code = "import time\ntime.sleep(20)"
    outcome = python_sandbox.execute(code)
    assert outcome["status"] == "error"
    assert "timed out" in outcome["stderr"]


@pytest.mark.asyncio
async def test_agent_and_tools_endpoints(setup_auth):
    token = setup_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-AIWA-Token": token}

        # 1. List tools
        tools_res = await client.get("/api/v1/agents/tools", headers=headers)
        assert tools_res.status_code == 200
        tools = tools_res.json()
        assert any(t["name"] == "execute_python" for t in tools)

        # 2. Create agent
        agent_res = await client.post(
            "/api/v1/agents",
            json={
                "name": "Data Analyst Agent",
                "system_prompt": "You analyze data using python.",
                "tools": ["execute_python"],
            },
            headers=headers,
        )
        assert agent_res.status_code == 200
        assert agent_res.json()["name"] == "Data Analyst Agent"

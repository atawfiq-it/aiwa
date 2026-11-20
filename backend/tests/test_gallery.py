import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import cleanup_session_token, generate_session_token
from app.main import app
from app.services.models.gallery import model_gallery
from app.supervisors.hardware_probe import hardware_probe


@pytest.fixture(autouse=True)
def setup_auth():
    token = generate_session_token()
    yield token
    cleanup_session_token()


def test_hardware_probe_cross_platform():
    hw = hardware_probe.detect_accelerator()
    assert "backend" in hw
    assert "device_name" in hw
    assert hw["total_vram_mb"] > 0


def test_gallery_yaml_loading():
    presets = model_gallery.load_presets()
    assert len(presets) >= 4
    assert any(p["id"] == "qwen2.5-vl-7b-instruct" for p in presets)


@pytest.mark.asyncio
async def test_gallery_api_endpoint(setup_auth):
    token = setup_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/models/gallery",
            headers={"X-AIWA-Token": token},
        )
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 4

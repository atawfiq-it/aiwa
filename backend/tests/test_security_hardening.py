import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.security import validate_safe_path
from app.main import create_app


def test_path_traversal_detection():
    allowed_dir = settings.UPLOADS_DIR
    dangerous_path = allowed_dir / ".." / "database" / "aiwa.db"

    with pytest.raises(HTTPException) as exc_info:
        validate_safe_path(dangerous_path, allowed_dir)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_production_mode_disables_docs(monkeypatch):
    # Set to production mode and instantiate fresh application
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    prod_app = create_app()

    async with AsyncClient(transport=ASGITransport(app=prod_app), base_url="http://test") as client:
        docs_res = await client.get("/docs")
        assert docs_res.status_code == 404
        redoc_res = await client.get("/redoc")
        assert redoc_res.status_code == 404

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app


@pytest.mark.asyncio
async def test_generic_exception_handler_does_not_expose_exception_text():
    app = create_app()

    @app.get("/explode")
    async def explode():
        raise RuntimeError("database password is secret")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/explode")

    payload = response.json()
    assert response.status_code == 500
    assert payload["success"] is False
    assert payload["trace_id"] is not None
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["error"]["message"] == "Internal server error"
    assert "reason" not in payload["error"]["details"]
    assert "database password is secret" not in response.text

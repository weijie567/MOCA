import pytest


@pytest.mark.asyncio
async def test_validation_errors_use_unified_format(client):
    response = await client.post("/api/v1/auth/login", json={"username": "admin_user"})
    payload = response.json()
    assert response.status_code == 422
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["trace_id"]

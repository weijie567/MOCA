import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["status"] == "healthy"
    assert payload["data"]["database"] == "connected"
    assert payload["trace_id"]

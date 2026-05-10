import pytest


@pytest.mark.asyncio
async def test_get_ticket_history_success(client, auth_headers):
    response = await client.get("/api/v1/tickets/TK-TEST-001", headers=await auth_headers("cs_zhang"))
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert len(payload["data"]["messages"]) == 2

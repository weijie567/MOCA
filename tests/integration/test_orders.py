import pytest


@pytest.mark.asyncio
async def test_get_order_success(client, auth_headers):
    response = await client.get("/api/v1/orders/ORD-TEST-001", headers=await auth_headers("cs_zhang"))
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["order_no"] == "ORD-TEST-001"
    assert "relation_hints" in payload["data"]

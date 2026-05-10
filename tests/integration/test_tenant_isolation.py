import pytest


@pytest.mark.asyncio
async def test_tenant_isolation_returns_not_found_for_other_tenant_order(client, auth_headers):
    response = await client.get("/api/v1/orders/ORD-OTHER-001", headers=await auth_headers("cs_zhang"))
    payload = response.json()
    assert response.status_code == 404
    assert payload["error"]["code"] == "ORDER_NOT_FOUND"


@pytest.mark.asyncio
async def test_merchant_cannot_access_other_merchant_order(client, auth_headers):
    response = await client.get("/api/v1/orders/ORD-OTHER-001", headers=await auth_headers("merchant_wang"))
    assert response.status_code in {403, 404}

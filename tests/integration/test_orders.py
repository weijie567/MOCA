import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("user_key", ["cs_zhang", "approval_manager", "merchant_wang"])
async def test_merchant_bound_users_can_get_same_merchant_order(client, auth_headers, user_key):
    response = await client.get("/api/v1/orders/ORD-TEST-001", headers=await auth_headers(user_key))
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["order_no"] == "ORD-TEST-001"
    assert "relation_hints" in payload["data"]


@pytest.mark.asyncio
@pytest.mark.parametrize("user_key", ["cs_zhang", "approval_manager", "merchant_wang"])
async def test_merchant_bound_users_cannot_get_other_same_tenant_order(client, auth_headers, user_key):
    response = await client.get("/api/v1/orders/ORD-TEST-002", headers=await auth_headers(user_key))
    payload = response.json()

    assert response.status_code == 403
    assert payload["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_get_other_same_tenant_order(client, auth_headers):
    response = await client.get("/api/v1/orders/ORD-TEST-002", headers=await auth_headers("admin_user"))
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["order_no"] == "ORD-TEST-002"


@pytest.mark.asyncio
async def test_other_tenant_user_gets_404_before_merchant_check(client, auth_headers):
    response = await client.get("/api/v1/orders/ORD-TEST-001", headers=await auth_headers("other_support"))
    payload = response.json()

    assert response.status_code == 404
    assert payload["error"]["code"] == "ORDER_NOT_FOUND"

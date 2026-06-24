import pytest


@pytest.mark.asyncio
async def test_get_refund_case_success(client, auth_headers):
    response = await client.get("/api/v1/refund-cases/RF-TEST-001", headers=await auth_headers("cs_zhang"))
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["refund_case_no"] == "RF-TEST-001"


@pytest.mark.asyncio
async def test_merchant_without_merchant_id_cannot_access_refund_case(client, auth_headers, seeded_session, session):
    seeded_session["users"]["merchant_wang"].merchant_id = None
    await session.commit()

    response = await client.get("/api/v1/refund-cases/RF-TEST-001", headers=await auth_headers("merchant_wang"))
    payload = response.json()

    assert response.status_code == 403
    assert payload["error"]["code"] == "FORBIDDEN"

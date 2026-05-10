import pytest


@pytest.mark.asyncio
async def test_get_refund_case_success(client, auth_headers):
    response = await client.get("/api/v1/refund-cases/RF-TEST-001", headers=await auth_headers("cs_zhang"))
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["refund_case_no"] == "RF-TEST-001"

from decimal import Decimal

import pytest

from src.db.models import RefundCase


@pytest.mark.asyncio
@pytest.mark.parametrize("user_key", ["cs_zhang", "approval_manager", "merchant_wang"])
async def test_merchant_bound_users_can_get_same_merchant_refund_case(client, auth_headers, user_key):
    response = await client.get("/api/v1/refund-cases/RF-TEST-001", headers=await auth_headers(user_key))
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["refund_case_no"] == "RF-TEST-001"


@pytest.mark.asyncio
@pytest.mark.parametrize("user_key", ["cs_zhang", "approval_manager", "merchant_wang"])
async def test_merchant_bound_users_cannot_get_other_same_tenant_refund_case(client, auth_headers, user_key):
    response = await client.get("/api/v1/refund-cases/RF-TEST-002", headers=await auth_headers(user_key))
    payload = response.json()

    assert response.status_code == 403
    assert payload["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_get_other_same_tenant_refund_case(client, auth_headers):
    response = await client.get("/api/v1/refund-cases/RF-TEST-002", headers=await auth_headers("admin_user"))
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["refund_case_no"] == "RF-TEST-002"


@pytest.mark.asyncio
async def test_other_tenant_user_gets_404_before_merchant_check(client, auth_headers):
    response = await client.get("/api/v1/refund-cases/RF-TEST-001", headers=await auth_headers("other_support"))
    payload = response.json()

    assert response.status_code == 404
    assert payload["error"]["code"] == "REFUND_CASE_NOT_FOUND"


@pytest.mark.asyncio
async def test_merchant_without_merchant_id_cannot_access_refund_case(client, auth_headers, seeded_session, session):
    seeded_session["users"]["merchant_wang"].merchant_id = None
    await session.commit()

    response = await client.get("/api/v1/refund-cases/RF-TEST-001", headers=await auth_headers("merchant_wang"))
    payload = response.json()

    assert response.status_code == 403
    assert payload["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_refund_case_with_cross_tenant_order_fails_closed(client, auth_headers, seeded_session, session):
    session.add(
        RefundCase(
            tenant_id=seeded_session["tenant"].id,
            order_id=seeded_session["other_order"].id,
            refund_case_no="RF-TEST-CROSS-ORDER",
            reason_code="quality_issue",
            reason_text="Cross-tenant order reference",
            status="reviewing",
            requested_amount=Decimal("10.00"),
        )
    )
    await session.commit()

    response = await client.get("/api/v1/refund-cases/RF-TEST-CROSS-ORDER", headers=await auth_headers("admin_user"))
    payload = response.json()

    assert response.status_code == 404
    assert payload["error"]["code"] == "REFUND_CASE_NOT_FOUND"

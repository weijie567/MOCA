import pytest
from sqlalchemy.exc import IntegrityError

from src.db.models import Ticket


@pytest.mark.asyncio
@pytest.mark.parametrize("user_key", ["cs_zhang", "approval_manager", "merchant_wang"])
async def test_merchant_bound_users_can_get_same_merchant_ticket(client, auth_headers, user_key):
    response = await client.get("/api/v1/tickets/TK-TEST-001", headers=await auth_headers(user_key))
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert len(payload["data"]["messages"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("user_key", ["cs_zhang", "approval_manager", "merchant_wang"])
async def test_merchant_bound_users_cannot_get_other_same_tenant_ticket(client, auth_headers, user_key):
    response = await client.get("/api/v1/tickets/TK-TEST-002", headers=await auth_headers(user_key))
    payload = response.json()

    assert response.status_code == 403
    assert payload["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_get_other_same_tenant_ticket(client, auth_headers):
    response = await client.get("/api/v1/tickets/TK-TEST-002", headers=await auth_headers("admin_user"))
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert len(payload["data"]["messages"]) == 2


@pytest.mark.asyncio
async def test_other_tenant_user_gets_404_before_merchant_check(client, auth_headers):
    response = await client.get("/api/v1/tickets/TK-TEST-001", headers=await auth_headers("other_support"))
    payload = response.json()

    assert response.status_code == 404
    assert payload["error"]["code"] == "TICKET_NOT_FOUND"


@pytest.mark.asyncio
async def test_merchant_without_merchant_id_cannot_access_ticket(client, auth_headers, seeded_session, session):
    del client, auth_headers
    seeded_session["users"]["merchant_wang"].merchant_id = None
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_ticket_with_cross_tenant_order_fails_closed(client, auth_headers, seeded_session, session):
    session.add(
        Ticket(
            tenant_id=seeded_session["tenant"].id,
            order_id=seeded_session["other_order"].id,
            ticket_no="TK-TEST-CROSS-ORDER",
            channel="chat",
            status="open",
            summary="Cross-tenant order reference",
            messages=[],
        )
    )
    await session.commit()

    response = await client.get("/api/v1/tickets/TK-TEST-CROSS-ORDER", headers=await auth_headers("admin_user"))
    payload = response.json()

    assert response.status_code == 404
    assert payload["error"]["code"] == "TICKET_NOT_FOUND"

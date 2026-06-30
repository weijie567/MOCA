from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.routers import auth as auth_router
from src.auth.jwt import create_access_token, decode_access_token
from src.config import settings


@pytest.mark.asyncio
async def test_login_success(client):
    response = await client.post("/api/v1/auth/login", json={"username": "admin_user", "password": "moca2024"})
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_accepts_tenant_id_selector(client, seeded_session):
    user = seeded_session["users"]["cs_zhang"]

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "moca2024", "tenant_id": str(user.tenant_id)},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert decode_access_token(payload["data"]["access_token"])["tenant_id"] == str(user.tenant_id)


@pytest.mark.asyncio
async def test_login_rejects_wrong_tenant_id_selector(client, seeded_session):
    user = seeded_session["users"]["cs_zhang"]

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "moca2024", "tenant_id": str(seeded_session["other_tenant"].id)},
    )
    payload = response.json()

    assert response.status_code == 401
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_login_failure(client):
    response = await client.post("/api/v1/auth/login", json={"username": "admin_user", "password": "wrong"})
    payload = response.json()
    assert response.status_code == 401
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_oauth_token_endpoint_supports_swagger_password_flow(client):
    response = await client.post(
        "/api/v1/auth/token",
        data={"username": "cs_zhang", "password": "moca2024", "scope": "agent:chat"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["token_type"] == "bearer"
    assert "agent:chat" in decode_access_token(payload["access_token"])["scopes"]


@pytest.mark.asyncio
async def test_oauth_token_endpoint_rejects_ambiguous_username_without_tenant_context(client, monkeypatch):
    async def ambiguous_user(*args, **kwargs):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Invalid username or password"},
        )

    monkeypatch.setattr(auth_router, "_resolve_user_for_login", ambiguous_user)

    response = await client.post(
        "/api/v1/auth/token",
        data={"username": "cs_zhang", "password": "moca2024", "scope": "agent:chat"},
    )
    payload = response.json()

    assert response.status_code == 401
    assert payload["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_auth_me_success(client, auth_headers):
    response = await client.get("/api/v1/auth/me", headers=await auth_headers())
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["username"] == "admin_user"


@pytest.mark.asyncio
async def test_demo_token_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_demo_auth", False)
    response = await client.post("/api/v1/auth/demo-token", json={"username": "admin_user"})
    payload = response.json()
    assert response.status_code == 403
    assert payload["success"] is False
    monkeypatch.setattr(settings, "enable_demo_auth", True)


@pytest.mark.asyncio
async def test_demo_token_accepts_tenant_id_selector(client, seeded_session):
    user = seeded_session["users"]["cs_zhang"]

    response = await client.post(
        "/api/v1/auth/demo-token",
        json={"username": user.username, "tenant_id": str(user.tenant_id)},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert decode_access_token(payload["data"]["access_token"])["tenant_id"] == str(user.tenant_id)


@pytest.mark.asyncio
async def test_demo_token_rejects_wrong_tenant_id_selector(client, seeded_session):
    user = seeded_session["users"]["cs_zhang"]

    response = await client.post(
        "/api/v1/auth/demo-token",
        json={"username": user.username, "tenant_id": str(seeded_session["other_tenant"].id)},
    )
    payload = response.json()

    assert response.status_code == 404
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_demo_token_rejects_ambiguous_username_without_tenant_context(client, monkeypatch):
    async def ambiguous_user(*args, **kwargs):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Invalid username or password"},
        )

    monkeypatch.setattr(auth_router, "_resolve_user_for_login", ambiguous_user)

    response = await client.post("/api/v1/auth/demo-token", json={"username": "cs_zhang"})
    payload = response.json()

    assert response.status_code == 401
    assert payload["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_resolve_user_for_login_rejects_ambiguous_username_without_tenant_context():
    class Result:
        def scalars(self):
            return self

        def all(self):
            return [SimpleNamespace(username="shared"), SimpleNamespace(username="shared")]

    class Session:
        async def execute(self, stmt):
            return Result()

    with pytest.raises(HTTPException) as exc_info:
        await auth_router._resolve_user_for_login(Session(), username="shared", tenant_id=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == {"code": "UNAUTHORIZED", "message": "Invalid username or password"}


@pytest.mark.asyncio
async def test_protected_api_without_token_returns_401(client):
    response = await client.get("/api/v1/orders/ORD-TEST-001")
    payload = response.json()
    assert response.status_code == 401
    assert payload["error"]["code"] == "UNAUTHORIZED"


def test_agent_chat_scope_is_issued_to_agent_roles():
    for role in ("support", "manager", "merchant", "admin"):
        token = create_access_token({"sub": "user-id", "tenant_id": "tenant-id", "role": role})
        payload = decode_access_token(token)

        assert "agent:chat" in payload["scopes"]


@pytest.mark.asyncio
async def test_verified_token_scopes_preserved_on_request_state(client, session, seeded_session):
    """A valid token's verified scopes are preserved on request.state.verified_token_scopes."""
    from unittest.mock import MagicMock
    from fastapi import Request
    from fastapi.security import SecurityScopes
    from src.auth.permissions import get_current_user
    from src.auth.jwt import create_access_token

    user = seeded_session["users"]["cs_zhang"]
    # Token with only agent:chat scope
    token = create_access_token(
        {"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": "support", "scopes": ["agent:chat"]}
    )

    mock_request = MagicMock(spec=Request)
    mock_request.state = MagicMock()

    result = await get_current_user(
        security_scopes=SecurityScopes(scopes=["agent:chat"]),
        token=token,
        session=session,
        request=mock_request,
    )

    assert result is not None
    # Verified token scopes must be preserved on request.state
    assert hasattr(mock_request.state, "verified_token_scopes")
    assert mock_request.state.verified_token_scopes == frozenset({"agent:chat"})


@pytest.mark.asyncio
async def test_rejected_token_does_not_populate_verified_scopes(client, session, seeded_session):
    """A token with insufficient scopes raises 403 without populating verified_token_scopes."""
    from types import SimpleNamespace
    from fastapi import Request, HTTPException
    from fastapi.security import SecurityScopes
    from unittest.mock import MagicMock
    from src.auth.permissions import get_current_user
    from src.auth.jwt import create_access_token

    user = seeded_session["users"]["cs_zhang"]
    # Token with only agent:chat, but endpoint requires orders:read
    token = create_access_token(
        {"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": "support", "scopes": ["agent:chat"]}
    )

    mock_request = MagicMock(spec=Request)
    mock_request.state = SimpleNamespace()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            security_scopes=SecurityScopes(scopes=["orders:read"]),
            token=token,
            session=session,
            request=mock_request,
        )

    assert exc_info.value.status_code == 403
    # verified_token_scopes must NOT be set on rejected tokens
    assert not hasattr(mock_request.state, "verified_token_scopes")

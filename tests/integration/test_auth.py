import pytest

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

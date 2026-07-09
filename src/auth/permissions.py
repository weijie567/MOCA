from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.common import FORBIDDEN, UNAUTHORIZED
from src.auth.jwt import ExpiredSignatureError, InvalidTokenError, decode_access_token
from src.db.models import User
from src.db.session import get_session
from src.platform.trusted_context import MERCHANT_BOUND_ROLES, PLATFORM_ADMIN_ROLES


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    scopes={
        "orders:read": "Read orders",
        "refunds:read": "Read refund cases",
        "tickets:read": "Read ticket histories",
        "knowledge:read": "Search policy knowledge base",
        "agent:chat": "Submit queries to the refund agent",
        "metrics:read": "Read scoped business metrics",
        "business:query": "Read scoped business queries",
        "approvals:review": "Review approvals",
        "memory:write": "Create admin memory preferences",
        "seed:write": "Run seed operations",
        "admin:debug": "Admin and debug operations",
    },
)
object.__setattr__(oauth2_scheme.model, "scopes", oauth2_scheme.model.flows.password.scopes)


async def get_current_user(
    request: Request,
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    auth_value = f'Bearer scope="{security_scopes.scope_str}"' if security_scopes.scopes else "Bearer"
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": UNAUTHORIZED, "message": "Could not validate credentials"},
        headers={"WWW-Authenticate": auth_value},
    )
    try:
        payload = decode_access_token(token)
    except (ExpiredSignatureError, InvalidTokenError) as exc:
        raise credentials_error from exc

    sub = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if not sub or not tenant_id:
        raise credentials_error

    stmt = select(User).where(User.id == uuid.UUID(str(sub)), User.tenant_id == uuid.UUID(str(tenant_id)))
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_error

    # Validate scopes claim is a collection of strings before preservation
    raw_scopes = payload.get("scopes", [])
    if not isinstance(raw_scopes, list) or not all(isinstance(s, str) for s in raw_scopes):
        raise credentials_error

    token_scopes = set(raw_scopes)
    missing_scopes = [scope for scope in security_scopes.scopes if scope not in token_scopes]
    if missing_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": FORBIDDEN, "message": "Insufficient scopes", "details": {"missing_scopes": missing_scopes}},
        )

    # Preserve verified token scopes in trusted request context (immutable)
    request.state.verified_token_scopes = frozenset(token_scopes)

    return user


def require_roles(allowed_roles: list[str]) -> Callable[..., User]:
    async def role_checker(user: User = Security(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": FORBIDDEN, "message": "Insufficient permissions"},
            )
        return user

    return role_checker


def require_merchant_access(user: User, merchant_id: object, *, resource_name: str = "resource") -> None:
    """Raise when a human business user cannot access the target merchant resource."""

    role = str(user.role)
    if role in PLATFORM_ADMIN_ROLES:
        return

    if role not in MERCHANT_BOUND_ROLES:
        _raise_merchant_access_forbidden(resource_name)

    user_merchant_id = getattr(user, "merchant_id", None)
    if user_merchant_id is None or str(user_merchant_id) != str(merchant_id):
        _raise_merchant_access_forbidden(resource_name)


def _raise_merchant_access_forbidden(resource_name: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": FORBIDDEN,
            "message": f"Merchant access is limited to the merchant's own {resource_name}",
        },
    )

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.common import FORBIDDEN, UNAUTHORIZED
from src.auth.jwt import ExpiredSignatureError, InvalidTokenError, decode_access_token
from src.db.models import User
from src.db.session import get_session


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scopes={
        "orders:read": "Read orders",
        "refunds:read": "Read refund cases",
        "tickets:read": "Read ticket histories",
        "knowledge:read": "Search policy knowledge base",
        "approvals:review": "Review approvals",
        "seed:write": "Run seed operations",
        "admin:debug": "Admin and debug operations",
    },
)


async def get_current_user(
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

    token_scopes = set(payload.get("scopes", []))
    missing_scopes = [scope for scope in security_scopes.scopes if scope not in token_scopes]
    if missing_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": FORBIDDEN, "message": "Insufficient scopes", "details": {"missing_scopes": missing_scopes}},
        )
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

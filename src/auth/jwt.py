from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from src.config import settings


ROLE_SCOPES: dict[str, list[str]] = {
    "support": ["orders:read", "refunds:read", "tickets:read", "knowledge:read", "agent:chat"],
    "manager": ["orders:read", "refunds:read", "tickets:read", "knowledge:read", "agent:chat", "approvals:review"],
    "merchant": ["orders:read", "refunds:read", "tickets:read", "knowledge:read", "agent:chat"],
    "admin": [
        "orders:read",
        "refunds:read",
        "tickets:read",
        "knowledge:read",
        "agent:chat",
        "approvals:review",
        "seed:write",
        "admin:debug",
    ],
}


def create_access_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    role = payload.get("role")
    payload.setdefault("scopes", ROLE_SCOPES.get(role, []))
    payload["exp"] = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


__all__ = [
    "ExpiredSignatureError",
    "InvalidTokenError",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]

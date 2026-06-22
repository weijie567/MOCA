"""Canonical trusted identity/scope context for platform service projections."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from src.auth.jwt import ROLE_SCOPES

TRUSTED_CONTEXT_SCHEMA_VERSION = "trusted_context.v1"
MERCHANT_SCOPE_SCHEMA_VERSION = "merchant_scope.v1"

SCOPE_TO_TOOL_PERMISSION = {
    "orders:read": "tool:get_order",
    "refunds:read": "tool:get_refund_case",
    "tickets:read": "tool:get_ticket",
    "knowledge:read": "tool:search_policy",
}


class MerchantScopeV1(BaseModel):
    """Merchant scope with deny-first, all-provided-dimensions semantics."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["merchant_scope.v1"] = MERCHANT_SCOPE_SCHEMA_VERSION
    merchant_ids: list[str]
    categories: list[str] | None = None
    risk_levels: list[str] | None = None
    match_rule: Literal["all_provided_dimensions"] = "all_provided_dimensions"

    @field_validator("merchant_ids", "categories", "risk_levels")
    @classmethod
    def _validate_scope_values(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("scope dimension must be a list")
        if not all(isinstance(item, str) and item for item in value):
            raise ValueError("scope dimension values must be non-empty strings")
        return value

    def allows(
        self,
        merchant_id: str | None = None,
        category: str | None = None,
        risk_level: str | None = None,
    ) -> bool:
        """Return whether every provided dimension is allowed by this scope."""

        if not self.merchant_ids:
            return False

        dimensions = (
            (merchant_id, self.merchant_ids),
            (category, self.categories),
            (risk_level, self.risk_levels),
        )
        for requested, allowed in dimensions:
            if requested is None:
                continue
            if not allowed:
                return False
            if "*" not in allowed and requested not in allowed:
                return False
        return True


class TrustedContext(BaseModel):
    """Canonical trusted context produced only from API/auth/run boundaries."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["trusted_context.v1"] = TRUSTED_CONTEXT_SCHEMA_VERSION
    tenant_id: str
    user_id: str
    role: str
    permissions: list[str]
    merchant_scope: MerchantScopeV1
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str | None = None
    locale: str | None = None


def merchant_scope_allows(
    scope: MerchantScopeV1 | dict[str, Any] | None,
    *,
    merchant_id: str | None = None,
    category: str | None = None,
    risk_level: str | None = None,
) -> bool:
    """Compatibility wrapper for MerchantScopeV1.allow checks."""

    if scope is None:
        return False
    parsed = scope if isinstance(scope, MerchantScopeV1) else MerchantScopeV1.model_validate(scope)
    return parsed.allows(merchant_id=merchant_id, category=category, risk_level=risk_level)


class TrustedContextFactory:
    """Factory for canonical trusted context from explicit trusted inputs."""

    @classmethod
    def create_from_request(
        cls,
        *,
        user: Any,
        verified_token_scopes: Iterable[str],
        thread_id: str,
        run_id: str,
        trace_id: str | None,
        session_id: str | None = None,
        locale: str | None = None,
        server_merchant_scope: MerchantScopeV1 | dict[str, Any] | None = None,
    ) -> TrustedContext:
        role = str(user.role)
        trusted_scopes = set(verified_token_scopes) & set(ROLE_SCOPES.get(role, []))
        permissions = [
            tool_permission
            for scope, tool_permission in SCOPE_TO_TOOL_PERMISSION.items()
            if scope in trusted_scopes
        ]
        merchant_scope = cls._merchant_scope_from_user(
            user,
            server_merchant_scope=server_merchant_scope,
        )

        return TrustedContext(
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            role=role,
            permissions=permissions,
            merchant_scope=merchant_scope,
            session_id=session_id,
            thread_id=str(thread_id),
            run_id=str(run_id),
            trace_id=trace_id,
            locale=locale,
        )

    @staticmethod
    def _merchant_scope_from_user(
        user: Any,
        *,
        server_merchant_scope: MerchantScopeV1 | dict[str, Any] | None,
    ) -> MerchantScopeV1:
        if server_merchant_scope is not None:
            return (
                server_merchant_scope
                if isinstance(server_merchant_scope, MerchantScopeV1)
                else MerchantScopeV1.model_validate(server_merchant_scope)
            )

        if str(user.role) == "merchant":
            merchant_id = getattr(user, "merchant_id", None)
            return MerchantScopeV1(merchant_ids=[str(merchant_id)] if merchant_id is not None else [])

        return MerchantScopeV1(merchant_ids=["*"])

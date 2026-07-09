"""Canonical trusted identity/scope context for platform service projections."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from src.auth.jwt import ROLE_SCOPES

TRUSTED_CONTEXT_SCHEMA_VERSION = "trusted_context.v1"
MERCHANT_SCOPE_SCHEMA_VERSION = "merchant_scope.v1"
MERCHANT_BOUND_ROLES = {"support", "manager", "merchant"}
PLATFORM_ADMIN_ROLES = {"admin"}
DEPRECATED_COMPATIBILITY_ROLES = {"merchant"}
ROLE_SCOPE_POLICY = {
    "support": "merchant_bound",
    "manager": "merchant_bound",
    "merchant": "deprecated_merchant_bound_compatibility",
    "admin": "platform_admin",
}

SCOPE_TO_TOOL_PERMISSION = {
    "orders:read": "tool:get_order",
    "refunds:read": "tool:get_refund_case",
    "tickets:read": "tool:get_ticket",
    "knowledge:read": "tool:search_policy",
    "metrics:read": "tool:query_business_metric",
}


def is_deprecated_compatibility_role(role: str) -> bool:
    return role in DEPRECATED_COMPATIBILITY_ROLES


def requires_business_merchant_binding(role: str, *, is_active: bool = True) -> bool:
    return is_active is True and role in MERCHANT_BOUND_ROLES


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
        server_tool_permissions: Iterable[str] | None = None,
    ) -> TrustedContext:
        role = str(user.role)
        trusted_scopes = set(verified_token_scopes) & set(ROLE_SCOPES.get(role, []))
        permissions = [
            tool_permission
            for scope, tool_permission in SCOPE_TO_TOOL_PERMISSION.items()
            if scope in trusted_scopes
        ]
        permissions = list(dict.fromkeys(permissions + cls._validated_server_tool_permissions(server_tool_permissions)))
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
        role = str(user.role)
        base_scope = TrustedContextFactory._base_merchant_scope_from_user(user, role=role)
        if server_merchant_scope is not None:
            override_scope = (
                server_merchant_scope
                if isinstance(server_merchant_scope, MerchantScopeV1)
                else MerchantScopeV1.model_validate(server_merchant_scope)
            )
            return TrustedContextFactory._narrow_merchant_scope(
                base_scope,
                override_scope,
                is_platform_admin=role in PLATFORM_ADMIN_ROLES,
            )

        return base_scope

    @staticmethod
    def _base_merchant_scope_from_user(user: Any, *, role: str) -> MerchantScopeV1:
        if role in MERCHANT_BOUND_ROLES:
            merchant_id = getattr(user, "merchant_id", None)
            if requires_business_merchant_binding(
                role,
                is_active=getattr(user, "is_active", True),
            ) and merchant_id is None:
                return MerchantScopeV1(merchant_ids=[])
            return MerchantScopeV1(merchant_ids=[str(merchant_id)] if merchant_id is not None else [])

        if role in PLATFORM_ADMIN_ROLES:
            return MerchantScopeV1(merchant_ids=["*"])

        return MerchantScopeV1(merchant_ids=[])

    @staticmethod
    def _narrow_merchant_scope(
        base_scope: MerchantScopeV1,
        override_scope: MerchantScopeV1,
        *,
        is_platform_admin: bool,
    ) -> MerchantScopeV1:
        if is_platform_admin:
            return override_scope

        if "*" in override_scope.merchant_ids:
            raise ValueError("server merchant scope cannot widen non-admin merchant scope")

        allowed_ids = set(base_scope.merchant_ids)
        requested_ids = set(override_scope.merchant_ids)
        if not requested_ids.issubset(allowed_ids):
            raise ValueError("server merchant scope cannot add merchant ids for non-admin actors")

        return override_scope

    @staticmethod
    def _validated_server_tool_permissions(values: Iterable[str] | None) -> list[str]:
        if values is None:
            return []
        permissions: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value.startswith("tool:"):
                raise ValueError("server tool permissions must be tool:* strings")
            if value in seen:
                continue
            seen.add(value)
            permissions.append(value)
        return permissions

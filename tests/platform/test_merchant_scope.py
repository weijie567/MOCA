from __future__ import annotations

import pytest
from pydantic import ValidationError
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException
from src.api.schemas.common import FORBIDDEN
from src.auth.permissions import require_merchant_access
from src.platform import trusted_context
from src.platform.trusted_context import (
    MerchantScopeV1,
    TrustedContextFactory,
    merchant_scope_allows,
    requires_business_merchant_binding,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_merchant_scope_schema_matches_contract_spec() -> None:
    scope = MerchantScopeV1(merchant_ids=["merchant-1"])

    assert set(MerchantScopeV1.model_fields) == {
        "schema_version",
        "merchant_ids",
        "categories",
        "risk_levels",
        "match_rule",
    }
    assert scope.schema_version == "merchant_scope.v1"
    assert scope.categories is None
    assert scope.risk_levels is None
    assert scope.match_rule == "all_provided_dimensions"


def test_merchant_scope_denies_empty_scope() -> None:
    scope = MerchantScopeV1(merchant_ids=[])

    assert merchant_scope_allows(scope, merchant_id="merchant-1") is False
    assert merchant_scope_allows(scope, category="electronics") is False
    assert merchant_scope_allows(scope, risk_level="high") is False


def test_merchant_scope_requires_explicit_wildcard() -> None:
    wildcard = MerchantScopeV1(merchant_ids=["*"])
    ordinary = MerchantScopeV1(merchant_ids=["merchant-1"])

    assert merchant_scope_allows(wildcard, merchant_id="merchant-999") is True
    assert merchant_scope_allows(ordinary, merchant_id="merchant-999") is False
    assert merchant_scope_allows(ordinary, merchant_id="merchant-1") is True


def test_merchant_scope_requires_all_provided_dimensions() -> None:
    scope = MerchantScopeV1(
        merchant_ids=["merchant-1"],
        categories=["refund"],
        risk_levels=["high"],
    )

    assert merchant_scope_allows(scope, merchant_id="merchant-1", category="refund", risk_level="high") is True
    assert merchant_scope_allows(scope, merchant_id="merchant-1", category="shipping", risk_level="high") is False
    assert merchant_scope_allows(scope, merchant_id="merchant-1", category="refund", risk_level="low") is False
    assert merchant_scope_allows(scope, merchant_id="merchant-2", category="refund", risk_level="high") is False


@pytest.mark.parametrize(
    "payload",
    [
        {"merchant_ids": [""]},
        {"merchant_ids": ["merchant-1"], "categories": [""]},
        {"merchant_ids": ["merchant-1"], "risk_levels": [""]},
        {"merchant_ids": ["merchant-1"], "match_rule": "any_dimension"},
        {"merchant_ids": ["merchant-1"], "source": "llm"},
        {"merchant_ids": ["merchant-1"], "user_supplied_scope": {"merchant_ids": ["*"]}},
    ],
)
def test_merchant_scope_rejects_invalid_values(payload: dict) -> None:
    with pytest.raises(ValidationError):
        MerchantScopeV1.model_validate(payload)


def _user(*, role: str, merchant_id: object | None) -> SimpleNamespace:
    return SimpleNamespace(role=role, merchant_id=merchant_id)


def _trusted_user(*, role: str, merchant_id: object | None = "merchant-primary") -> SimpleNamespace:
    return SimpleNamespace(
        id="user-primary",
        tenant_id="tenant-primary",
        role=role,
        merchant_id=merchant_id,
    )


def test_role_scope_policy_marks_legacy_merchant_as_deprecated_compatibility() -> None:
    assert trusted_context.MERCHANT_BOUND_ROLES == {"support", "manager", "merchant"}
    assert trusted_context.PLATFORM_ADMIN_ROLES == {"admin"}
    assert trusted_context.DEPRECATED_COMPATIBILITY_ROLES == {"merchant"}
    assert trusted_context.ROLE_SCOPE_POLICY == {
        "support": "merchant_bound",
        "manager": "merchant_bound",
        "merchant": "deprecated_merchant_bound_compatibility",
        "admin": "platform_admin",
    }
    assert trusted_context.is_deprecated_compatibility_role("merchant") is True
    assert trusted_context.is_deprecated_compatibility_role("support") is False


@pytest.mark.parametrize("role", ["support", "manager", "merchant"])
def test_human_business_roles_are_merchant_bound_and_never_wildcard(role: str) -> None:
    context = TrustedContextFactory.create_from_request(
        user=_trusted_user(role=role, merchant_id="merchant-primary"),
        verified_token_scopes=[],
        thread_id="thread-1",
        run_id="run-1",
        trace_id=None,
    )

    assert context.merchant_scope.merchant_ids == ["merchant-primary"]
    assert "*" not in context.merchant_scope.merchant_ids


def test_admin_is_only_human_role_with_wildcard_business_scope() -> None:
    admin_context = TrustedContextFactory.create_from_request(
        user=_trusted_user(role="admin", merchant_id=None),
        verified_token_scopes=[],
        thread_id="thread-1",
        run_id="run-1",
        trace_id=None,
    )
    unknown_context = TrustedContextFactory.create_from_request(
        user=_trusted_user(role="approval_manager", merchant_id="merchant-primary"),
        verified_token_scopes=[],
        thread_id="thread-1",
        run_id="run-2",
        trace_id=None,
    )

    assert admin_context.merchant_scope.merchant_ids == ["*"]
    assert unknown_context.merchant_scope.merchant_ids == []


@pytest.mark.parametrize("role", ["support", "manager", "merchant"])
def test_active_business_users_without_merchant_id_receive_deny_all_scope(role: str) -> None:
    context = TrustedContextFactory.create_from_request(
        user=_trusted_user(role=role, merchant_id=None),
        verified_token_scopes=[],
        thread_id="thread-1",
        run_id=f"run-missing-merchant-{role}",
        trace_id=None,
    )

    assert requires_business_merchant_binding(role, is_active=True) is True
    assert context.merchant_scope == MerchantScopeV1(merchant_ids=[])


def test_inactive_legacy_merchant_rows_do_not_require_active_binding() -> None:
    assert requires_business_merchant_binding("merchant", is_active=False) is False


def test_non_admin_wildcard_server_merchant_scope_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot widen non-admin merchant scope"):
        TrustedContextFactory.create_from_request(
            user=_trusted_user(role="support", merchant_id="merchant-primary"),
            verified_token_scopes=[],
            thread_id="thread-1",
            run_id="run-wildcard-rejected",
            trace_id=None,
            server_merchant_scope={"merchant_ids": ["*"]},
        )


def test_manager_is_not_tenant_wide_supervisor_for_business_access() -> None:
    """manager is not tenant-wide for merchant business data."""

    with pytest.raises(HTTPException) as exc_info:
        require_merchant_access(
            _user(role="manager", merchant_id="merchant-primary"),
            "merchant-other",
            resource_name="orders",
        )

    assert exc_info.value.status_code == 403


def test_seed_roles_mark_merchant_as_deprecated_compatibility() -> None:
    seed_source = (PROJECT_ROOT / "scripts" / "seed_demo.py").read_text(encoding="utf-8")

    assert "Deprecated compatibility role" in seed_source
    assert "support-equivalent" in seed_source
    assert "not a recommended new role" in seed_source
    assert seed_source.count('"merchant", merchants[') == 1


def test_require_merchant_access_allows_admin_cross_merchant() -> None:
    require_merchant_access(_user(role="admin", merchant_id=None), "merchant-target", resource_name="orders")


@pytest.mark.parametrize("role", ["support", "manager", "merchant"])
def test_require_merchant_access_allows_merchant_bound_same_merchant(role: str) -> None:
    merchant_id = UUID("00000000-0000-0000-0000-000000000001")

    require_merchant_access(_user(role=role, merchant_id=merchant_id), str(merchant_id), resource_name="orders")


@pytest.mark.parametrize("role", ["support", "manager", "merchant"])
def test_require_merchant_access_denies_active_business_user_missing_binding(role: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_merchant_access(_user(role=role, merchant_id=None), "merchant-target", resource_name="orders")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == FORBIDDEN


@pytest.mark.parametrize(
    ("role", "actor_merchant_id", "target_merchant_id"),
    [
        ("support", None, "merchant-target"),
        ("manager", "merchant-primary", "merchant-other"),
        ("merchant", "merchant-primary", "merchant-other"),
        ("supervisor", "merchant-primary", "merchant-primary"),
    ],
)
def test_require_merchant_access_fails_closed(
    role: str,
    actor_merchant_id: object | None,
    target_merchant_id: object,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_merchant_access(
            _user(role=role, merchant_id=actor_merchant_id),
            target_merchant_id,
            resource_name="orders",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == FORBIDDEN

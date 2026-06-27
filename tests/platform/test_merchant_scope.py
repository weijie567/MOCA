from __future__ import annotations

import pytest
from pydantic import ValidationError
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException
from src.api.schemas.common import FORBIDDEN
from src.auth.permissions import require_merchant_access
from src.platform.trusted_context import MerchantScopeV1, merchant_scope_allows


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


def test_require_merchant_access_allows_admin_cross_merchant() -> None:
    require_merchant_access(_user(role="admin", merchant_id=None), "merchant-target", resource_name="orders")


@pytest.mark.parametrize("role", ["support", "manager", "merchant"])
def test_require_merchant_access_allows_merchant_bound_same_merchant(role: str) -> None:
    merchant_id = UUID("00000000-0000-0000-0000-000000000001")

    require_merchant_access(_user(role=role, merchant_id=merchant_id), str(merchant_id), resource_name="orders")


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

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.auth.jwt import ROLE_SCOPES, create_access_token, decode_access_token
from src.auth.permissions import oauth2_scheme
from src.platform.trusted_context import TrustedContextFactory


def _user(**overrides: object) -> SimpleNamespace:
    values = {
        "tenant_id": "tenant-auth",
        "id": "user-auth",
        "role": "support",
        "merchant_id": "merchant-primary",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _factory_kwargs(**overrides: object) -> dict:
    values = {
        "user": _user(),
        "verified_token_scopes": frozenset({"orders:read", "knowledge:read", "agent:chat", "seed:write"}),
        "session_id": "session-server",
        "thread_id": "thread-server",
        "run_id": "run-server",
        "trace_id": "trace-server",
        "locale": "zh-CN",
    }
    values.update(overrides)
    return values


def test_factory_uses_authenticated_user_verified_scopes_and_server_ids() -> None:
    context = TrustedContextFactory.create_from_request(**_factory_kwargs())

    assert context.schema_version == "trusted_context.v1"
    assert context.tenant_id == "tenant-auth"
    assert context.user_id == "user-auth"
    assert context.role == "support"
    assert context.session_id == "session-server"
    assert context.thread_id == "thread-server"
    assert context.run_id == "run-server"
    assert context.trace_id == "trace-server"
    assert context.locale == "zh-CN"
    assert set(context.permissions) == {"tool:get_order", "tool:search_policy"}
    assert context.merchant_scope.merchant_ids == ["merchant-primary"]


@pytest.mark.parametrize(
    "override_kwargs",
    [
        {"tenant_id": "tenant-from-request"},
        {"user_id": "user-from-request"},
        {"role": "admin"},
        {"permissions": ["tool:execute_refund"]},
        {"merchant_scope": {"merchant_ids": ["*"]}},
        {"request_payload": {"tenant_id": "tenant-from-body", "merchant_scope": {"merchant_ids": ["*"]}}},
        {"llm_output": {"permissions": ["tool:execute_refund"], "merchant_scope": {"merchant_ids": ["*"]}}},
    ],
)
def test_factory_rejects_user_payload_and_llm_override_kwargs(override_kwargs: dict) -> None:
    kwargs = _factory_kwargs() | override_kwargs

    with pytest.raises((TypeError, ValueError)):
        TrustedContextFactory.create_from_request(**kwargs)


def test_factory_preserves_agent_runs_permission_intersection() -> None:
    manager = _user(role="manager", merchant_id="merchant-manager")
    context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(
            user=manager,
            verified_token_scopes=frozenset({"approvals:review", "seed:write", "admin:debug", "knowledge:read"}),
        )
    )

    assert set(context.permissions) == {"tool:search_policy"}
    assert "seed:write" not in context.permissions
    assert "admin:debug" not in context.permissions
    assert context.merchant_scope.merchant_ids == ["merchant-manager"]


def test_factory_maps_metrics_read_to_business_metric_tool_permission_only_by_intersection() -> None:
    support = _user(role="support", merchant_id="merchant-support")

    context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(user=support, verified_token_scopes=frozenset({"metrics:read"}))
    )
    assert "tool:query_business_metric" in context.permissions
    assert context.merchant_scope.merchant_ids == ["merchant-support"]

    missing_token_scope = TrustedContextFactory.create_from_request(
        **_factory_kwargs(user=support, verified_token_scopes=frozenset({"orders:read"}))
    )
    assert "tool:query_business_metric" not in missing_token_scope.permissions

    unknown_role = TrustedContextFactory.create_from_request(
        **_factory_kwargs(
            user=_user(role="approval_manager", merchant_id="merchant-support"),
            verified_token_scopes=frozenset({"metrics:read"}),
        )
    )
    assert "tool:query_business_metric" not in unknown_role.permissions
    assert unknown_role.merchant_scope.merchant_ids == []


@pytest.mark.parametrize("role", ["support", "manager", "admin"])
def test_business_query_scope_is_issued_to_authorized_staff_roles(role: str) -> None:
    token = create_access_token({"sub": "user-id", "tenant_id": "tenant-id", "role": role})
    payload = decode_access_token(token)

    assert "business:query" in ROLE_SCOPES[role]
    assert "business:query" in payload["scopes"]
    assert "metrics:read" in payload["scopes"]


def test_deprecated_merchant_role_keeps_metric_scope_without_business_query_default() -> None:
    token = create_access_token({"sub": "user-id", "tenant_id": "tenant-id", "role": "merchant"})
    payload = decode_access_token(token)

    assert "metrics:read" in payload["scopes"]
    assert "business:query" not in payload["scopes"]


def test_oauth_password_flow_advertises_business_query_scope() -> None:
    assert oauth2_scheme.model.flows.password.scopes["business:query"] == "Read scoped business queries"


@pytest.mark.parametrize(
    ("role", "merchant_id", "expected_scope"),
    [
        ("support", "merchant-support", ["merchant-support"]),
        ("manager", "merchant-manager", ["merchant-manager"]),
        ("admin", None, ["*"]),
    ],
)
def test_factory_maps_business_query_scope_to_business_query_tool_permission_for_authorized_roles(
    role: str,
    merchant_id: str | None,
    expected_scope: list[str],
) -> None:
    context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(
            user=_user(role=role, merchant_id=merchant_id),
            verified_token_scopes=frozenset({"business:query", "metrics:read"}),
        )
    )

    assert "tool:business_query" in context.permissions
    assert "tool:query_business_metric" in context.permissions
    assert context.merchant_scope.merchant_ids == expected_scope


def test_factory_keeps_business_query_and_metric_permissions_on_separate_trusted_scopes() -> None:
    support = _user(role="support", merchant_id="merchant-support")

    business_context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(user=support, verified_token_scopes=frozenset({"business:query"}))
    )
    assert "tool:business_query" in business_context.permissions
    assert "tool:query_business_metric" not in business_context.permissions

    metric_context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(user=support, verified_token_scopes=frozenset({"metrics:read"}))
    )
    assert "tool:query_business_metric" in metric_context.permissions
    assert "tool:business_query" not in metric_context.permissions

    missing_trusted_scope = TrustedContextFactory.create_from_request(
        **_factory_kwargs(user=support, verified_token_scopes=frozenset({"orders:read"}))
    )
    assert "tool:business_query" not in missing_trusted_scope.permissions

    unknown_role = TrustedContextFactory.create_from_request(
        **_factory_kwargs(
            user=_user(role="approval_manager", merchant_id="merchant-support"),
            verified_token_scopes=frozenset({"business:query"}),
        )
    )
    assert "tool:business_query" not in unknown_role.permissions
    assert unknown_role.merchant_scope.merchant_ids == []


@pytest.mark.parametrize(
    "override_kwargs",
    [
        {"permissions": ["tool:business_query"]},
        {"request_payload": {"permissions": ["tool:business_query"], "scopes": ["business:query"]}},
        {"llm_output": {"permissions": ["tool:business_query"], "scopes": ["business:query"]}},
        {"tool_args": {"permissions": ["tool:business_query"], "business_scope": {"merchant_ids": ["*"]}}},
        {"frontend_payload": {"verified_token_scopes": ["business:query"], "permissions": ["tool:business_query"]}},
    ],
)
def test_factory_rejects_untrusted_business_query_permission_injection(override_kwargs: dict) -> None:
    kwargs = _factory_kwargs(verified_token_scopes=frozenset()) | override_kwargs

    with pytest.raises((TypeError, ValueError)):
        TrustedContextFactory.create_from_request(**kwargs)


def test_factory_merchant_metrics_scope_is_own_bound_only() -> None:
    context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(
            user=_user(role="merchant", merchant_id="merchant-legacy"),
            verified_token_scopes=frozenset({"metrics:read"}),
        )
    )

    assert context.permissions == ["tool:query_business_metric"]
    assert context.merchant_scope.merchant_ids == ["merchant-legacy"]

    with pytest.raises(ValueError):
        TrustedContextFactory.create_from_request(
            **_factory_kwargs(
                user=_user(role="merchant", merchant_id="merchant-legacy"),
                verified_token_scopes=frozenset({"metrics:read"}),
                server_merchant_scope={"merchant_ids": ["*"]},
            )
        )


def test_factory_accepts_explicit_server_tool_permissions_without_token_scope_widening() -> None:
    manager = _user(role="manager", merchant_id="merchant-manager")
    context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(
            user=manager,
            verified_token_scopes=frozenset(),
            server_tool_permissions=["tool:create_coupon_grant_draft"],
        )
    )

    assert context.permissions == ["tool:create_coupon_grant_draft"]
    assert context.merchant_scope.merchant_ids == ["merchant-manager"]


def test_factory_rejects_non_tool_server_permissions() -> None:
    with pytest.raises(ValueError):
        TrustedContextFactory.create_from_request(**_factory_kwargs(server_tool_permissions=["approvals:review"]))


@pytest.mark.parametrize(
    ("role", "merchant_id", "expected_scope"),
    [
        ("support", "merchant-support", ["merchant-support"]),
        ("manager", "merchant-manager", ["merchant-manager"]),
        ("merchant", "merchant-legacy", ["merchant-legacy"]),
        ("support", None, []),
        ("manager", None, []),
        ("merchant", None, []),
        ("supervisor", "merchant-ghost", []),
        ("approval_manager", "merchant-ghost", []),
    ],
)
def test_factory_derives_merchant_bound_and_unknown_role_scopes(
    role: str,
    merchant_id: str | None,
    expected_scope: list[str],
) -> None:
    context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(user=_user(role=role, merchant_id=merchant_id))
    )

    assert context.merchant_scope.merchant_ids == expected_scope


def test_factory_derives_admin_wildcard_scope() -> None:
    context = TrustedContextFactory.create_from_request(**_factory_kwargs(user=_user(role="admin")))

    assert context.merchant_scope.merchant_ids == ["*"]


def test_factory_allows_non_admin_server_scope_narrowing_only_to_base_scope() -> None:
    context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(
            user=_user(role="support", merchant_id="merchant-primary"),
            server_merchant_scope={"merchant_ids": ["merchant-primary"]},
        )
    )

    assert context.merchant_scope.merchant_ids == ["merchant-primary"]


@pytest.mark.parametrize(
    "server_merchant_scope",
    [
        {"merchant_ids": ["*"]},
        {"merchant_ids": ["other-merchant"]},
    ],
)
def test_factory_rejects_non_admin_server_scope_widening(server_merchant_scope: dict) -> None:
    with pytest.raises(ValueError):
        TrustedContextFactory.create_from_request(
            **_factory_kwargs(
                user=_user(role="support", merchant_id="merchant-primary"),
                server_merchant_scope=server_merchant_scope,
            )
        )


def test_factory_allows_admin_server_scope_narrowing() -> None:
    context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(
            user=_user(role="admin"),
            server_merchant_scope={"merchant_ids": ["merchant-primary"]},
        )
    )

    assert context.merchant_scope.merchant_ids == ["merchant-primary"]

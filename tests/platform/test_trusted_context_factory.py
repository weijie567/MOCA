from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.platform.trusted_context import TrustedContextFactory


def _user(**overrides: object) -> SimpleNamespace:
    values = {
        "tenant_id": "tenant-auth",
        "id": "user-auth",
        "role": "support",
        "merchant_id": None,
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
    assert context.merchant_scope.merchant_ids == ["*"]


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
    manager = _user(role="manager")
    context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(
            user=manager,
            verified_token_scopes=frozenset({"approvals:review", "seed:write", "admin:debug", "knowledge:read"}),
        )
    )

    assert set(context.permissions) == {"tool:search_policy"}
    assert "seed:write" not in context.permissions
    assert "admin:debug" not in context.permissions
    assert context.merchant_scope.merchant_ids == ["*"]


def test_factory_accepts_explicit_server_tool_permissions_without_token_scope_widening() -> None:
    manager = _user(role="manager")
    context = TrustedContextFactory.create_from_request(
        **_factory_kwargs(
            user=manager,
            verified_token_scopes=frozenset(),
            server_tool_permissions=["tool:create_coupon_grant_draft"],
        )
    )

    assert context.permissions == ["tool:create_coupon_grant_draft"]


def test_factory_rejects_non_tool_server_permissions() -> None:
    with pytest.raises(ValueError):
        TrustedContextFactory.create_from_request(
            **_factory_kwargs(server_tool_permissions=["approvals:review"])
        )

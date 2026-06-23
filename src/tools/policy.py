"""Tool policy engine for visibility and runtime authorization decisions."""

from __future__ import annotations

import re
from typing import Any

from src.platform.trusted_context import MerchantScopeV1
from src.tools.catalog import ToolCatalog, ToolDescriptor
from src.tools.contracts import (
    ToolCallContext,
    ToolPolicyDecision,
    ToolViewV1,
)

TOOL_POLICY_CORE_REASON_CODES: frozenset[str] = frozenset({
    "visible",
    "hidden_by_policy",
    "caller_not_allowed",
    "missing_permission",
    "scope_denied",
    "side_effect_blocked",
    "schema_invalid",
    "approval_required",
    "safety_snapshot_required",
    "idempotency_required",
    "tool_unavailable",
})

TOOL_POLICY_RUNTIME_ONLY_REASON_CODES: frozenset[str] = frozenset({
    "schema_invalid",
    "approval_required",
    "safety_snapshot_required",
    "idempotency_required",
})

TOOL_POLICY_EXTENSION_REASON_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

# Schema shape keys retained during prompt-safe projection.
_PROMPT_SAFE_SCHEMA_KEYS: set[str] = {
    "type",
    "properties",
    "items",
    "required",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "enum",
    "description",
    "additionalProperties",
}

# Keys that must be stripped from field-level schemas.
_INTERNAL_SCHEMA_KEYS: set[str] = {
    "default",
    "examples",
    "x-internal",
    "x-permission",
    "x-resource-policy",
    "x-adapter",
    "required_permission",
    "caller_allowlist",
    "side_effect",
    "executor",
}

_RESOURCE_BINDING_KEYS: set[str] = {
    "tenant_id",
    "merchant_id",
    "order_id",
    "order_no",
    "refund_id",
    "refund_case_no",
    "ticket_id",
}

# Identifiers that require domain lookup for ownership proof.
_DOMAIN_SCOPE_CHECK_IDENTIFIERS: set[str] = {
    "order_id",
    "order_no",
    "refund_id",
    "refund_case_no",
    "ticket_id",
}


def validate_tool_policy_reason_codes(codes: list[str]) -> None:
    """Validate that reason codes are either core or namespaced extension codes.

    Freeform unknown non-namespaced codes are rejected in the tool-policy
    contract path.
    """

    for code in codes:
        if code in TOOL_POLICY_CORE_REASON_CODES:
            continue
        if TOOL_POLICY_EXTENSION_REASON_PATTERN.fullmatch(code):
            continue
        raise ValueError(
            f"reason_code {code!r} is not a core code and does not match "
            f"the namespaced extension pattern '<namespace>.<snake_case>'"
        )


def project_prompt_safe_input_schema(raw_schema: dict[str, Any]) -> dict[str, Any]:
    """Project a raw input schema into a prompt-safe representation.

    Retains only shape keys (type, properties, items, required, constraints,
    description, additionalProperties) and strips defaults, examples, and all
    descriptor/policy/adapter metadata.
    """

    return _project_schema_node(raw_schema)


def _project_schema_node(node: dict[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key, value in node.items():
        if key in _INTERNAL_SCHEMA_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            projected[key] = {
                prop_name: _project_schema_node(prop_schema)
                for prop_name, prop_schema in value.items()
            }
            continue
        if key == "items" and isinstance(value, dict):
            projected[key] = _project_schema_node(value)
            continue
        if key == "additionalProperties":
            if isinstance(value, dict):
                projected[key] = _project_schema_node(value)
            elif isinstance(value, bool):
                projected[key] = value
            # Other types (e.g. stray strings) are conservatively dropped.
            continue
        if key in _PROMPT_SAFE_SCHEMA_KEYS:
            projected[key] = value
    return projected


class ToolPolicyEngine:
    """Owns visibility and runtime auth decisions.

    Does NOT call executors, write graph state, write conversation records,
    or construct prompts.
    """

    def __init__(
        self,
        catalog: ToolCatalog | None = None,
        *,
        policy_version: str = "tool_policy.v1",
    ) -> None:
        self._catalog = catalog or ToolCatalog()
        self._policy_version = policy_version

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def visibility_decisions(
        self,
        *,
        caller: str,
        ctx: ToolCallContext,
        availability_map: dict[str, bool] | None = None,
    ) -> list[ToolPolicyDecision]:
        """Return one visibility decision per catalog descriptor.

        When *availability_map* is provided, tools whose availability is
        ``False`` receive a ``hidden`` decision with ``tool_unavailable``
        reason so the decision record captures unavailability even though
        the tool is not surfaced in the planner prompt.
        """

        available = availability_map or {}
        decisions: list[ToolPolicyDecision] = []
        for descriptor in self._catalog.descriptors():
            is_available = available.get(descriptor.name, True)
            decisions.append(
                self._visibility_decision(descriptor, caller=caller, runtime_available=is_available)
            )
        return decisions

    def _visibility_decision(
        self,
        descriptor: ToolDescriptor,
        *,
        caller: str,
        runtime_available: bool = True,
    ) -> ToolPolicyDecision:
        reason_codes: list[str] = []
        visible = True

        if not runtime_available:
            visible = False
            reason_codes.append("tool_unavailable")

        if descriptor.exposure != "planner_visible":
            visible = False
            if "hidden_by_policy" not in reason_codes:
                reason_codes.append("hidden_by_policy")

        if caller not in descriptor.caller_allowlist:
            visible = False
            if "hidden_by_policy" not in reason_codes:
                reason_codes.append("caller_not_allowed")

        if not reason_codes:
            reason_codes.append("visible")

        availability_summary = None
        if not runtime_available:
            availability_summary = f"Tool {descriptor.name!r} is currently unavailable"

        return ToolPolicyDecision(
            tool_name=descriptor.name,
            caller=caller,
            decision_stage="visibility",
            decision="visible" if visible else "hidden",
            reason_codes=reason_codes,
            required_scopes=[descriptor.required_permission],
            matched_scope=None,
            policy_version=self._policy_version,
            data_classification="internal",
            resource_scope_binding=None,
            runtime_available=runtime_available,
            availability_summary=availability_summary,
        )

    def tool_views_for_decisions(
        self,
        decisions: list[ToolPolicyDecision],
        *,
        availability_map: dict[str, bool] | None = None,
    ) -> list[ToolViewV1]:
        """Return ToolViewV1 objects only for visible and available tools."""

        available = availability_map or {}
        views: list[ToolViewV1] = []
        for decision in decisions:
            if decision.decision != "visible":
                continue
            is_available = available.get(decision.tool_name, True)
            if not is_available:
                continue
            descriptor = self._catalog.descriptor(decision.tool_name)
            if descriptor is None:
                continue
            views.append(self._build_tool_view(descriptor))
        return views

    def _build_tool_view(self, descriptor: ToolDescriptor) -> ToolViewV1:
        safe_notes: list[str] = []
        if descriptor.kind == "write":
            safe_notes.append("This is a write tool; it must not be called directly.")
        if descriptor.requires_approval:
            safe_notes.append("This tool requires approval before execution.")
        if descriptor.requires_safety_snapshot:
            safe_notes.append("A safety snapshot is required before execution.")
        if descriptor.requires_idempotency_key:
            safe_notes.append("An idempotency key is required.")

        return ToolViewV1(
            name=descriptor.name,
            description=descriptor.description,
            input_schema=project_prompt_safe_input_schema(descriptor.input_schema),
            safe_usage_notes=safe_notes,
            result_contract_version="tool_result.v2",
        )

    # ------------------------------------------------------------------
    # Runtime auth
    # ------------------------------------------------------------------

    def runtime_auth(
        self,
        *,
        tool_name: str,
        args: dict[str, Any],
        ctx: ToolCallContext,
        availability_map: dict[str, bool] | None = None,
    ) -> ToolPolicyDecision:
        """Validate caller, permission, side-effect, scope, and required fields."""

        available = availability_map or {}
        descriptor = self._catalog.descriptor(tool_name)

        if descriptor is None:
            return self._denied_decision(
                tool_name=tool_name,
                caller=ctx.caller_node,
                reason_codes=["tool_unavailable"],
                required_scopes=[],
                runtime_available=False,
                availability_summary=f"Tool {tool_name!r} is not registered",
            )

        is_available = available.get(tool_name, True)
        if not is_available:
            return self._denied_decision(
                tool_name=tool_name,
                caller=ctx.caller_node,
                reason_codes=["tool_unavailable"],
                required_scopes=[descriptor.required_permission],
                runtime_available=False,
                availability_summary=f"Tool {tool_name!r} is currently unavailable",
            )

        reason_codes: list[str] = []

        # Caller allowlist
        if ctx.caller_node not in descriptor.caller_allowlist:
            reason_codes.append("caller_not_allowed")

        # Permission
        if descriptor.required_permission not in ctx.permissions:
            reason_codes.append("missing_permission")

        # Side-effect gate for write tools.
        # action_draft callers are allowed to execute write tools (their purpose).
        if descriptor.side_effect == "write":
            if not (ctx.caller_node == "action_draft" and descriptor.kind == "write"):
                reason_codes.append("side_effect_blocked")

        # Merchant scope binding
        resource_scope_binding = self._build_resource_binding(args, ctx)
        if resource_scope_binding.get("_scope_denied"):
            reason_codes.append("scope_denied")

        # Required fields
        if descriptor.requires_approval and not ctx.approval_ref:
            reason_codes.append("approval_required")
        if descriptor.requires_safety_snapshot and not ctx.safety_snapshot_ref:
            reason_codes.append("safety_snapshot_required")
        if descriptor.requires_idempotency_key and not ctx.idempotency_key:
            reason_codes.append("idempotency_required")

        if reason_codes:
            return self._denied_decision(
                tool_name=tool_name,
                caller=ctx.caller_node,
                reason_codes=reason_codes,
                required_scopes=[descriptor.required_permission],
                resource_scope_binding=resource_scope_binding,
                runtime_available=True,
            )

        return ToolPolicyDecision(
            tool_name=tool_name,
            caller=ctx.caller_node,
            decision_stage="runtime_auth",
            decision="allowed",
            reason_codes=["visible"],
            required_scopes=[descriptor.required_permission],
            matched_scope=descriptor.required_permission,
            policy_version=self._policy_version,
            data_classification="internal",
            resource_scope_binding=resource_scope_binding,
            runtime_available=True,
            availability_summary=None,
        )

    def _denied_decision(
        self,
        *,
        tool_name: str,
        caller: str,
        reason_codes: list[str],
        required_scopes: list[str],
        resource_scope_binding: dict[str, Any] | None = None,
        runtime_available: bool | None = None,
        availability_summary: str | None = None,
    ) -> ToolPolicyDecision:
        return ToolPolicyDecision(
            tool_name=tool_name,
            caller=caller,
            decision_stage="runtime_auth",
            decision="denied",
            reason_codes=reason_codes,
            required_scopes=required_scopes,
            matched_scope=None,
            policy_version=self._policy_version,
            data_classification="internal",
            resource_scope_binding=resource_scope_binding,
            runtime_available=runtime_available,
            availability_summary=availability_summary,
        )

    def _build_resource_binding(
        self,
        args: dict[str, Any],
        ctx: ToolCallContext,
    ) -> dict[str, Any]:
        """Build resource bindings and check explicit merchant scope."""

        binding: dict[str, Any] = {}
        scope_denied = False

        for key in _RESOURCE_BINDING_KEYS:
            value = args.get(key)
            if value is None:
                continue
            binding[key] = value

            # Explicit merchant_id must be checked against scope
            if key == "merchant_id":
                merchant_scope = ctx.merchant_scope
                try:
                    if isinstance(merchant_scope, MerchantScopeV1):
                        scope = merchant_scope
                    elif isinstance(merchant_scope, list):
                        scope = MerchantScopeV1(merchant_ids=merchant_scope)
                    else:
                        scope = MerchantScopeV1.model_validate(merchant_scope)
                except (TypeError, ValueError):
                    scope_denied = True
                else:
                    if not scope.allows(merchant_id=str(value)):
                        scope_denied = True

            # Domain-lookup identifiers require Phase 30 ownership proof
            if key in _DOMAIN_SCOPE_CHECK_IDENTIFIERS:
                binding["requires_domain_scope_check"] = True

        if scope_denied:
            binding["_scope_denied"] = True

        return binding

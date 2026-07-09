from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutableActionDescriptor:
    action_type: str
    aliases: frozenset[str]


@dataclass(frozen=True, slots=True)
class ActionResolution:
    raw_value: str
    executable_action_type: str | None
    disposition: str | None
    matched_alias: str | None
    match_kind: str


@dataclass(frozen=True, slots=True)
class RiskVocabulary:
    raw_risk_level: str | None
    risk_severity: str
    risk_disposition: str
    legacy_risk_level: str | None = None
    approval_required: bool = False


@dataclass(frozen=True, slots=True)
class PreRouteActionMatch:
    raw_text: str
    executable_action_type: str | None
    matched_alias: str
    alias_group: str
    requested_operation: str
    reason_code: str


def _read_only_mapping[T](values: Mapping[str, T]) -> Mapping[str, T]:
    return MappingProxyType(dict(values))


def _normalized_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _alias_matches(text: str, alias: str) -> bool:
    normalized_alias = alias.strip().lower()
    if not normalized_alias:
        return False
    return normalized_alias in text


_EXECUTABLE_ACTION_DESCRIPTORS: tuple[ExecutableActionDescriptor, ...] = (
    ExecutableActionDescriptor(
        action_type="issue_coupon",
        aliases=frozenset(
            {
                "issue_coupon",
                "coupon",
                "compensation",
                "compensate",
                "补偿",
                "券",
                "赔付",
            }
        ),
    ),
    ExecutableActionDescriptor(
        action_type="full_refund",
        aliases=frozenset(
            {
                "full_refund",
                "full refund",
                "全额退款",
                "全额退",
                "整单退款",
            }
        ),
    ),
    ExecutableActionDescriptor(
        action_type="partial_refund",
        aliases=frozenset(
            {
                "partial_refund",
                "partial refund",
                "部分退款",
            }
        ),
    ),
    ExecutableActionDescriptor(
        action_type="approve_refund",
        aliases=frozenset(
            {
                "approve_refund",
                "refund",
                "退款",
            }
        ),
    ),
)

EXECUTABLE_ACTION_TYPES = frozenset(descriptor.action_type for descriptor in _EXECUTABLE_ACTION_DESCRIPTORS)
NON_EXECUTABLE_DISPOSITIONS = frozenset({"manual_review", "blocked"})
RISK_SEVERITIES = frozenset({"low", "medium", "high"})
RISK_DISPOSITIONS = frozenset({"allow", "approval_required", "manual_review", "blocked"})

_DISPOSITION_ALIASES: Mapping[str, frozenset[str]] = {
    "manual_review": frozenset({"manual_review", "reject", "rejected", "拒绝", "不建议", "无法支持"}),
    "blocked": frozenset({"blocked"}),
}

_PRE_ROUTE_ACTION_ALIASES: Mapping[str, frozenset[str]] = {
    "direct_execution": frozenset({"execute", "override", "执行", "创建"}),
    "refund": frozenset({"refund now", "直接退款"}),
    "coupon": frozenset({"发券"}),
}

_PRE_ROUTE_GROUP_ACTION_TYPES: Mapping[str, str | None] = {
    "direct_execution": None,
    "refund": "approve_refund",
    "coupon": "issue_coupon",
}

_APPROVAL_ID_RE = re.compile(r"\b(?:APR|APPROVAL|审批)[-_]?\d+\b", re.IGNORECASE)
_APPROVAL_OR_ACTION_SHORT_REPLY_KEYS = frozenset(
    {
        "同意",
        "批准",
        "确认",
        "执行",
        "approve",
        "approved",
        "accept",
        "accepted",
        "yes",
        "goahead",
        "doit",
    }
)


def _short_text_key(text: str) -> str:
    return re.sub(r"[\s。！!,.，、；;：:]+", "", text.strip()).lower()


def _approval_chat_hard_negative(text: str) -> bool:
    lowered = text.lower()
    if _short_text_key(text) in _APPROVAL_OR_ACTION_SHORT_REPLY_KEYS:
        return True

    approval_command = any(token in lowered for token in ("approval", "apr-")) or "审批" in text
    approval_action = any(
        token in lowered
        for token in (
            "approve",
            "approved",
            "accept",
            "accepted",
            "reject",
            "rejected",
            "yes",
            "goahead",
            "go ahead",
            "doit",
            "do it",
        )
    ) or any(token in text for token in ("同意", "批准", "确认", "通过", "拒绝"))
    approval_context = bool(_APPROVAL_ID_RE.search(text)) or "approval" in lowered or "审批" in text
    return approval_command or (approval_action and approval_context)


class SafetyTaxonomyRegistry:
    def __init__(
        self,
        *,
        executable_actions: tuple[ExecutableActionDescriptor, ...],
        dispositions: Mapping[str, frozenset[str]],
        risk_severities: frozenset[str],
        risk_dispositions: frozenset[str],
        pre_route_alias_groups: Mapping[str, frozenset[str]],
    ) -> None:
        self._executable_actions = _read_only_mapping(
            {descriptor.action_type: descriptor for descriptor in executable_actions}
        )
        self._dispositions = _read_only_mapping(dispositions)
        self._risk_severities = risk_severities
        self._risk_dispositions = risk_dispositions
        self._pre_route_alias_groups = _read_only_mapping(pre_route_alias_groups)
        self._action_aliases = _read_only_mapping(
            {
                alias.strip().lower(): descriptor.action_type
                for descriptor in executable_actions
                for alias in descriptor.aliases
            }
        )
        self._ordered_action_aliases = tuple(
            (descriptor.action_type, alias)
            for descriptor in executable_actions
            for alias in sorted(descriptor.aliases, key=len, reverse=True)
        )
        self._ordered_disposition_aliases = tuple(
            (disposition, alias)
            for disposition, aliases in dispositions.items()
            for alias in sorted(aliases, key=len, reverse=True)
        )

    def executable_actions(self) -> Mapping[str, ExecutableActionDescriptor]:
        return self._executable_actions

    def executable_action_types(self) -> frozenset[str]:
        return frozenset(self._executable_actions)

    def non_executable_dispositions(self) -> frozenset[str]:
        return frozenset(self._dispositions)

    def risk_severities(self) -> frozenset[str]:
        return self._risk_severities

    def risk_dispositions(self) -> frozenset[str]:
        return self._risk_dispositions

    def action_aliases_for(self, action_type: str) -> frozenset[str]:
        descriptor = self._executable_actions.get(action_type)
        if descriptor is None:
            return frozenset()
        return descriptor.aliases

    def pre_route_action_aliases(self) -> Mapping[str, frozenset[str]]:
        return self._pre_route_alias_groups

    def resolve_action_text(self, value: Any) -> ActionResolution:
        raw_value = str(value or "")
        text = raw_value.strip()
        lowered = text.lower()
        if not text:
            return ActionResolution(raw_value=raw_value, executable_action_type=None, disposition=None, matched_alias=None, match_kind="none")

        if lowered in self._executable_actions:
            return ActionResolution(
                raw_value=raw_value,
                executable_action_type=lowered,
                disposition=None,
                matched_alias=lowered,
                match_kind="exact",
            )
        if lowered in self._dispositions:
            return ActionResolution(
                raw_value=raw_value,
                executable_action_type=None,
                disposition=lowered,
                matched_alias=lowered,
                match_kind="disposition",
            )

        for disposition, alias in self._ordered_disposition_aliases:
            if _alias_matches(lowered, alias):
                return ActionResolution(
                    raw_value=raw_value,
                    executable_action_type=None,
                    disposition=disposition,
                    matched_alias=alias,
                    match_kind="disposition",
                )

        for action_type, alias in self._ordered_action_aliases:
            if _alias_matches(lowered, alias):
                return ActionResolution(
                    raw_value=raw_value,
                    executable_action_type=action_type,
                    disposition=None,
                    matched_alias=alias,
                    match_kind="alias" if alias != action_type else "exact",
                )

        return ActionResolution(
            raw_value=raw_value,
            executable_action_type=None,
            disposition="manual_review",
            matched_alias=None,
            match_kind="default",
        )

    def detect_pre_route_action_request(self, text: str) -> PreRouteActionMatch | None:
        raw_text = text or ""
        if _approval_chat_hard_negative(raw_text):
            return None

        lowered = raw_text.lower()
        for group, aliases in self._pre_route_alias_groups.items():
            for alias in sorted(aliases, key=len, reverse=True):
                if _alias_matches(lowered, alias):
                    resolution = self.resolve_action_text(raw_text)
                    executable_action_type = resolution.executable_action_type or _PRE_ROUTE_GROUP_ACTION_TYPES[group]
                    return PreRouteActionMatch(
                        raw_text=raw_text,
                        executable_action_type=executable_action_type,
                        matched_alias=alias,
                        alias_group=group,
                        requested_operation="execute_action",
                        reason_code="critical_write",
                    )
        return None

    def matches_action_alias(self, action_type: str, text: str) -> bool:
        lowered = str(text or "").lower()
        return any(_alias_matches(lowered, alias) for alias in self.action_aliases_for(action_type))


SAFETY_TAXONOMY = SafetyTaxonomyRegistry(
    executable_actions=_EXECUTABLE_ACTION_DESCRIPTORS,
    dispositions=_DISPOSITION_ALIASES,
    risk_severities=RISK_SEVERITIES,
    risk_dispositions=RISK_DISPOSITIONS,
    pre_route_alias_groups=_PRE_ROUTE_ACTION_ALIASES,
)


def action_aliases_for(action_type: str) -> frozenset[str]:
    return SAFETY_TAXONOMY.action_aliases_for(action_type)


def pre_route_action_aliases() -> Mapping[str, frozenset[str]]:
    return SAFETY_TAXONOMY.pre_route_action_aliases()


def resolve_action_text(value: Any) -> ActionResolution:
    return SAFETY_TAXONOMY.resolve_action_text(value)


def canonical_executable_action_type(value: Any) -> str | None:
    return resolve_action_text(value).executable_action_type


def is_executable_action_type(value: Any) -> bool:
    return _normalized_text(value) in EXECUTABLE_ACTION_TYPES


def is_actionable_recommendation(value: Any) -> bool:
    return resolve_action_text(value).executable_action_type is not None


def detect_pre_route_action_request(text: str) -> PreRouteActionMatch | None:
    return SAFETY_TAXONOMY.detect_pre_route_action_request(text)


def matches_full_refund_alias(text: str) -> bool:
    return SAFETY_TAXONOMY.matches_action_alias("full_refund", text)


def matches_compensation_alias(text: str) -> bool:
    return SAFETY_TAXONOMY.matches_action_alias("issue_coupon", text)


def normalize_risk_vocabulary(value: Mapping[str, Any] | str | None) -> RiskVocabulary:
    payload = dict(value) if isinstance(value, Mapping) else {"risk_level": value}
    raw_risk_level = str(payload.get("risk_level") or "").strip().lower()
    raw_severity = str(payload.get("risk_severity") or payload.get("severity") or "").strip().lower()
    raw_disposition = str(payload.get("risk_disposition") or payload.get("disposition") or "").strip().lower()
    approval_required = payload.get("approval_required") is True

    legacy_risk_level = raw_risk_level if raw_risk_level in NON_EXECUTABLE_DISPOSITIONS else None
    if raw_disposition in RISK_DISPOSITIONS:
        risk_disposition = raw_disposition
    elif raw_risk_level in NON_EXECUTABLE_DISPOSITIONS:
        risk_disposition = raw_risk_level
    elif approval_required:
        risk_disposition = "approval_required"
    else:
        risk_disposition = "allow"

    if raw_severity in RISK_SEVERITIES:
        risk_severity = raw_severity
    elif raw_risk_level in RISK_SEVERITIES:
        risk_severity = raw_risk_level
    elif raw_risk_level == "blocked":
        risk_severity = "high"
    elif raw_risk_level == "manual_review":
        risk_severity = "medium"
    else:
        risk_severity = "medium"

    return RiskVocabulary(
        raw_risk_level=raw_risk_level or None,
        risk_severity=risk_severity,
        risk_disposition=risk_disposition,
        legacy_risk_level=legacy_risk_level,
        approval_required=approval_required,
    )


def risk_assessment_with_disposition(
    assessment: Mapping[str, Any] | None,
    *,
    disposition: str | None = None,
    severity: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    payload = dict(assessment or {})
    if disposition is not None:
        payload["risk_disposition"] = disposition
    if severity is not None:
        payload["risk_severity"] = severity
    vocabulary = normalize_risk_vocabulary(payload)
    payload["risk_level"] = vocabulary.risk_severity
    payload["risk_severity"] = vocabulary.risk_severity
    payload["risk_disposition"] = vocabulary.risk_disposition
    if vocabulary.legacy_risk_level is not None:
        payload["legacy_risk_level"] = vocabulary.legacy_risk_level
    if reason:
        existing_reason_codes = payload.get("reason_codes")
        reason_codes = list(existing_reason_codes) if isinstance(existing_reason_codes, list) else []
        if reason not in reason_codes:
            reason_codes.append(reason)
        payload["reason_codes"] = reason_codes
    return payload


__all__ = [
    "EXECUTABLE_ACTION_TYPES",
    "NON_EXECUTABLE_DISPOSITIONS",
    "RISK_DISPOSITIONS",
    "RISK_SEVERITIES",
    "SAFETY_TAXONOMY",
    "ActionResolution",
    "ExecutableActionDescriptor",
    "PreRouteActionMatch",
    "RiskVocabulary",
    "SafetyTaxonomyRegistry",
    "action_aliases_for",
    "canonical_executable_action_type",
    "detect_pre_route_action_request",
    "is_actionable_recommendation",
    "is_executable_action_type",
    "matches_compensation_alias",
    "matches_full_refund_alias",
    "normalize_risk_vocabulary",
    "pre_route_action_aliases",
    "resolve_action_text",
    "risk_assessment_with_disposition",
]

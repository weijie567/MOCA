"""Deterministic hard-rule checks for material claim verification."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


RULE_CODES = (
    "negation_conflict",
    "condition_branch_unmet",
    "amount_threshold_unmet",
    "time_window_unmet",
    "exception_clause_applies",
    "policy_hierarchy_conflict",
)


class DomainRuleVerifier:
    """Run rules-first checks that semantic review cannot override."""

    def verify(
        self,
        *,
        claim_text: str,
        evidence_snippets: Sequence[Mapping[str, Any]],
        claim_metadata: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        metadata = claim_metadata or {}
        return [
            _rule_result("negation_conflict", not _has_negation_conflict(claim_text, evidence_snippets, metadata)),
            _rule_result("condition_branch_unmet", not _condition_branch_unmet(evidence_snippets, metadata)),
            _rule_result("amount_threshold_unmet", not _amount_threshold_unmet(evidence_snippets, metadata)),
            _rule_result("time_window_unmet", not _time_window_unmet(evidence_snippets, metadata)),
            _rule_result("exception_clause_applies", not _exception_clause_applies(evidence_snippets, metadata)),
            _rule_result("policy_hierarchy_conflict", not _policy_hierarchy_conflict(evidence_snippets, metadata)),
        ]


def failed_rule_reason_codes(rule_checks: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return stable reason codes for failed hard checks."""
    return [
        str(check.get("reason_code") or check.get("rule") or "")
        for check in rule_checks
        if check.get("passed") is False and str(check.get("reason_code") or check.get("rule") or "")
    ]


def _rule_result(rule: str, passed: bool) -> dict[str, Any]:
    return {
        "rule": rule,
        "passed": passed,
        "reason_code": rule,
        "hard_gate": True,
    }


def _has_negation_conflict(
    claim_text: str,
    evidence_snippets: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
) -> bool:
    if _flag(metadata.get("negation_conflict")):
        return True
    claim = _normalize(claim_text)
    evidence = _normalize(" ".join(str(snippet.get("text") or "") for snippet in evidence_snippets))
    if any(_flag(snippet.get("negation_conflict")) for snippet in evidence_snippets):
        return True
    if _claim_affirms_eligibility(claim) and _evidence_denies_eligibility(evidence):
        return True
    if _claim_affirms_allowed_action(claim) and _evidence_denies_allowed_action(evidence):
        return True
    return bool(_contains_cjk_allow(claim) and _contains_cjk_deny(evidence))


def _condition_branch_unmet(evidence_snippets: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]) -> bool:
    if _flag(metadata.get("condition_branch_unmet")):
        return True
    required = set(_metadata_list(metadata.get("required_conditions")))
    for snippet in evidence_snippets:
        required.update(_metadata_list(snippet.get("required_conditions")))
    if not required:
        return False
    met = set(_metadata_list(metadata.get("conditions_met")))
    return not required.issubset(met)


def _amount_threshold_unmet(evidence_snippets: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]) -> bool:
    if _flag(metadata.get("amount_threshold_unmet")):
        return True
    amount = _number(metadata.get("amount") or metadata.get("claim_amount"))
    if amount is None:
        return False
    for snippet in evidence_snippets:
        threshold = snippet.get("amount_threshold")
        if not isinstance(threshold, Mapping):
            continue
        maximum = _number(threshold.get("max"))
        minimum = _number(threshold.get("min"))
        if maximum is not None and amount > maximum:
            return True
        if minimum is not None and amount < minimum:
            return True
    return False


def _time_window_unmet(evidence_snippets: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]) -> bool:
    if _flag(metadata.get("time_window_unmet")):
        return True
    elapsed_days = _number(
        metadata.get("days_since_event") or metadata.get("days_since_delivery") or metadata.get("elapsed_days")
    )
    if elapsed_days is None:
        return False
    for snippet in evidence_snippets:
        window = snippet.get("time_window")
        if not isinstance(window, Mapping):
            continue
        maximum = _number(window.get("max_days"))
        minimum = _number(window.get("min_days"))
        if maximum is not None and elapsed_days > maximum:
            return True
        if minimum is not None and elapsed_days < minimum:
            return True
    return False


def _exception_clause_applies(evidence_snippets: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]) -> bool:
    if _flag(metadata.get("exception_clause_applies")):
        return True
    flags = set(_metadata_list(metadata.get("exception_flags")))
    if not flags:
        return False
    exceptions: set[str] = set()
    for snippet in evidence_snippets:
        exceptions.update(_metadata_list(snippet.get("exceptions")))
    return bool(flags & exceptions)


def _policy_hierarchy_conflict(evidence_snippets: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]) -> bool:
    if _flag(metadata.get("policy_hierarchy_conflict")):
        return True
    for snippet in evidence_snippets:
        hierarchy = snippet.get("policy_hierarchy")
        if isinstance(hierarchy, Mapping) and _flag(hierarchy.get("conflict")):
            return True
    return False


def _claim_affirms_eligibility(text: str) -> bool:
    return bool(re.search(r"\b(is|are|be|become|remains?)\s+eligible\b|\beligible\b", text)) and not bool(
        re.search(r"\bnot\s+eligible\b|\bineligible\b", text)
    )


def _evidence_denies_eligibility(text: str) -> bool:
    return bool(re.search(r"\bnot\s+eligible\b|\bineligible\b|\bno\s+eligibility\b", text))


def _claim_affirms_allowed_action(text: str) -> bool:
    return bool(re.search(r"\ballow(?:ed|s)?\b|\bmust\s+issue\b|\bcan\s+issue\b|\bshould\s+issue\b", text)) and not (
        _evidence_denies_allowed_action(text)
    )


def _evidence_denies_allowed_action(text: str) -> bool:
    return bool(
        re.search(r"\bnot\s+allowed\b|\bmust\s+not\b|\bshould\s+not\b|\bprohibit(?:ed|s)?\b|\bforbidden\b", text)
    )


def _contains_cjk_allow(text: str) -> bool:
    return any(token in text for token in ("允许", "可以", "可补偿", "可赔付", "符合"))


def _contains_cjk_deny(text: str) -> bool:
    return any(token in text for token in ("不允许", "不可", "不能", "不得", "禁止", "不予", "不符合"))


def _normalize(value: str) -> str:
    return " ".join(str(value).casefold().split())


def _flag(value: Any) -> bool:
    return value is True or str(value).casefold() in {"true", "1", "yes"}


def _metadata_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

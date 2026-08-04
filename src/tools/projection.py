"""Tool result projection into normalized, prompt, audit, and debug surfaces."""

from __future__ import annotations

from typing import Any

from src.business.query.projection import business_query_response_text, safe_business_query_metadata
from src.tools.contracts import ToolResultProjectionV1, ToolResultV2

# Keys that must never appear in normalized or prompt surfaces.
_RAW_SENTINEL_KEYS: set[str] = {
    "raw",
    "raw_payload",
    "raw_tool_payload",
    "raw_tool_output",
    "raw_args",
    "private_reasoning",
    "approval_authority_body",
    "debug_trace",
    "secret",
    "pii",
}

# Safe scalar keys extracted from result.data into normalized_result.
_SAFE_SCALAR_KEYS: set[str] = {
    "order_no",
    "id",
    "status",
    "merchant_id",
    "source_system",
    "summary",
    "best_score",
    "retrieval_status",
    "draft_id",
    "created",
    "idempotent_reused",
    "refund_case_no",
    "ticket_id",
    "ticket_no",
    "tracking_no",
}

_POLICY_EVIDENCE_REF_KEYS: set[str] = {
    "policy_id",
    "policy_version",
    "evidence_type",
}

_RELATION_HINT_KEYS: set[str] = {
    "has_active_refund",
    "latest_refund_case_id",
    "has_open_ticket",
    "latest_ticket_id",
    "tracking_no",
    "merchant_id",
}

_METRIC_RESULT_KEYS: set[str] = {
    "metric_id",
    "status",
    "value",
    "rate",
    "numerator",
    "denominator",
    "unit",
    "display_value",
    "scope",
    "time_range",
    "filters",
    "freshness",
    "formula",
    "caveats",
    "no_leak_status",
}

_MAX_TEXT_FOR_PROMPT = 500


class ToolResultProjector:
    """Produces separated projection layers from a ToolResultV2.

    Four layers:
    - normalized_result: safe typed surfaces for graph/service state
    - prompt_projection: structured fields for LLM prompts
    - audit_refs / resource_refs: linking refs for replay/conversation
    - debug_projection: safe booleans/counts for tests/diagnostics

    Does NOT emit events and does NOT create artifact storage.
    """

    def project(
        self,
        tool_name: str,
        result: ToolResultV2,
        tool_call_id: str,
        tool_result_id: str | None = None,
        raw_result_ref: str | None = None,
        raw_result_hash: str | None = None,
        policy_decision_ref: str | None = None,
    ) -> ToolResultProjectionV1:
        data = result.data or {}

        normalized = self._build_normalized_result(data, result)
        prompt_proj = self._build_prompt_projection(
            tool_name=tool_name,
            result=result,
            normalized=normalized,
            tool_call_id=tool_call_id,
        )
        text_for_prompt = self._build_text_for_prompt(prompt_proj)
        audit_refs = self._build_audit_refs(result, tool_call_id, policy_decision_ref)
        resource_refs = self._build_resource_refs(result)
        debug_proj = self._build_debug_projection(data, result)

        return ToolResultProjectionV1(
            normalized_result=normalized,
            prompt_projection=prompt_proj,
            text_for_prompt=text_for_prompt,
            audit_refs=audit_refs,
            resource_refs=resource_refs,
            debug_projection=debug_proj,
            raw_artifact_ref=raw_result_ref,
            raw_artifact_hash=raw_result_hash,
        )

    # ------------------------------------------------------------------
    # Normalized result
    # ------------------------------------------------------------------

    def _build_normalized_result(
        self,
        data: dict[str, Any],
        result: ToolResultV2,
    ) -> dict[str, Any]:
        normalized: dict[str, Any] = {}

        # Status and source from the result envelope.
        normalized["status"] = result.status
        normalized["source_system"] = result.source_system

        # Bounded summary from the result envelope.
        normalized["summary"] = result.summary[:500] if result.summary else ""

        # Safe scalar fields from data.
        for key in _SAFE_SCALAR_KEYS:
            if key in data and isinstance(data[key], (str, int, float, bool)):
                normalized[key] = data[key]

        policy_refs = self._extract_policy_evidence_refs(data)
        if policy_refs:
            normalized["policy_evidence_refs"] = policy_refs

        relation_hints = self._extract_relation_hints(data)
        if relation_hints:
            normalized["relation_hints"] = relation_hints

        metric_result = self._extract_metric_result(data)
        if metric_result:
            normalized.update(metric_result)

        business_query = self._extract_business_query_result(data)
        if business_query:
            normalized["business_query"] = business_query

        # Refs from the ToolResultV2 envelope (not from data).
        if result.business_fact_refs:
            normalized["business_fact_refs"] = self._business_fact_refs_from_envelope(result)
        if result.policy_evidence_refs:
            normalized["policy_evidence_refs"] = [
                {"evidence_id": ref.evidence_id, "doc_key": ref.doc_key} for ref in result.policy_evidence_refs
            ]

        # Audit ref from the result envelope.
        if result.audit_ref:
            normalized["audit_ref"] = result.audit_ref

        # Error surface (safe only).
        if result.error is not None:
            normalized["error"] = {
                "code": result.error.code,
                "safe_message": result.error.safe_message,
                "retryable": result.error.retryable,
                "source": result.error.source,
            }

        # Case-memory items (sanitized). Check both canonical and legacy keys.
        case_memory = data.get("_case_memory_items") or data.get("items")
        if isinstance(case_memory, list):
            normalized["_case_memory_items"] = self._sanitize_case_memory(case_memory)

        return normalized

    def _business_fact_refs_from_envelope(self, result: ToolResultV2) -> list[dict[str, Any]]:
        return [
            {"resource_type": ref.resource_type, "resource_id": ref.resource_id} for ref in result.business_fact_refs
        ]

    def _extract_policy_evidence_refs(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for key in _POLICY_EVIDENCE_REF_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value:
                refs.append({"ref_type": key, "ref_id": value})
        return refs

    def _extract_relation_hints(self, data: dict[str, Any]) -> dict[str, Any]:
        hints = data.get("relation_hints")
        if not isinstance(hints, dict):
            return {}
        safe_hints: dict[str, Any] = {}
        for key in _RELATION_HINT_KEYS:
            if key not in hints:
                continue
            value = hints.get(key)
            if value is None or isinstance(value, (str, int, float, bool)):
                safe_hints[key] = value
        return safe_hints

    def _sanitize_case_memory(self, items: list[Any]) -> list[dict[str, Any]]:
        sanitized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            safe_entry: dict[str, Any] = {}
            for key in (
                "case_id",
                "case_memory_id",
                "memory_id",
                "id",
                "similarity",
                "score",
                "snippet",
                "excerpt",
                "outcome",
                "applicability",
                "caveats",
            ):
                if key in item:
                    value = item[key]
                    if isinstance(value, (str, int, float, bool)):
                        safe_entry[key] = value
            # Sanitize nested ref lists.
            for key in ("policy_refs", "source_refs"):
                refs = item.get(key)
                if isinstance(refs, list):
                    safe_refs = self._sanitize_ref_list(refs)
                    if safe_refs:
                        safe_entry[key] = safe_refs
            if safe_entry:
                sanitized.append(safe_entry)
        return sanitized

    def _sanitize_ref_list(self, refs: list[Any]) -> list[dict[str, Any]]:
        safe_refs: list[dict[str, Any]] = []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            safe_ref = {
                str(key): value
                for key, value in ref.items()
                if str(key).lower() not in _RAW_SENTINEL_KEYS and isinstance(value, (str, int, float, bool))
            }
            if safe_ref:
                safe_refs.append(safe_ref)
        return safe_refs

    # ------------------------------------------------------------------
    # Prompt projection
    # ------------------------------------------------------------------

    def _build_prompt_projection(
        self,
        *,
        tool_name: str,
        result: ToolResultV2,
        normalized: dict[str, Any],
        tool_call_id: str,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        safe_error = None
        if result.error is not None:
            safe_error = {
                "code": result.error.code,
                "safe_message": result.error.safe_message,
            }

        redaction_applied = _has_raw_sentinels_in_dict(result.data or {})
        metric_summary = self._metric_prompt_summary(normalized)
        business_query_summary = self._business_query_prompt_summary(normalized)
        summary = (
            business_query_summary["text"]
            if business_query_summary
            else metric_summary["text"]
            if metric_summary
            else normalized.get("summary", result.summary[:500])
        )

        prompt_projection = {
            "tool_name": tool_name,
            "status": result.status,
            "summary": summary,
            "business_fact_refs": normalized.get("business_fact_refs", []),
            "policy_candidate_refs": normalized.get("policy_evidence_refs", []),
            "resource_refs": normalized.get("business_fact_refs", []),
            "relation_hints": normalized.get("relation_hints", {}),
            "warnings": warnings,
            "safe_error": safe_error,
            "redaction_applied": redaction_applied,
            "text_for_prompt": "",  # filled by _build_text_for_prompt
        }
        if business_query_summary:
            prompt_projection["business_query_summary"] = business_query_summary
        if metric_summary:
            prompt_projection["metric_summary"] = metric_summary
        return prompt_projection

    def _extract_metric_result(self, data: dict[str, Any]) -> dict[str, Any]:
        if not _looks_like_metric_result(data):
            return {}

        metric: dict[str, Any] = {
            "metric_id": data["metric_id"],
            "metric_status": data["status"],
            "unit": data["unit"],
            "display_value": data["display_value"],
        }
        for key in ("value", "rate", "numerator", "denominator"):
            value = data.get(key)
            if value is None or isinstance(value, (int, float)):
                metric[key] = value

        scope = data.get("scope")
        if isinstance(scope, dict):
            merchant_ids = scope.get("merchant_ids")
            merchant_count = len(merchant_ids) if isinstance(merchant_ids, list) and "*" not in merchant_ids else None
            metric["scope"] = {
                "scope_label": scope.get("scope_label") if isinstance(scope.get("scope_label"), str) else None,
                "merchant_count": merchant_count,
                "is_wildcard": isinstance(merchant_ids, list) and "*" in merchant_ids,
            }

        time_range = data.get("time_range")
        if isinstance(time_range, dict):
            metric["time_range"] = {
                key: value
                for key, value in time_range.items()
                if key in {"start_at", "end_at", "preset", "timezone"} and (value is None or isinstance(value, str))
            }

        filters = data.get("filters")
        if isinstance(filters, dict):
            status_filter = filters.get("status_filter")
            metric["filters"] = {
                "status_filter": [item for item in status_filter if isinstance(item, str)]
                if isinstance(status_filter, list)
                else [],
                "merchant_filter_applied": isinstance(filters.get("merchant_id"), str),
            }

        caveats = data.get("caveats")
        if isinstance(caveats, list):
            metric["caveats"] = [item for item in caveats if isinstance(item, str)][:5]

        formula = data.get("formula")
        if isinstance(formula, str) and not _contains_sqlish_token(formula):
            metric["formula"] = formula[:240]

        return metric

    def _extract_business_query_result(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = data.get("business_query")
        if not isinstance(payload, dict):
            return {}
        try:
            return safe_business_query_metadata(payload)
        except ValueError:
            return {}

    @staticmethod
    def _metric_prompt_summary(normalized: dict[str, Any]) -> dict[str, Any] | None:
        metric_id = normalized.get("metric_id")
        display_value = normalized.get("display_value")
        if not isinstance(metric_id, str) or not isinstance(display_value, str):
            return None
        metric_status = normalized.get("metric_status")
        unit = normalized.get("unit")
        time_range = normalized.get("time_range")
        time_preset = time_range.get("preset") if isinstance(time_range, dict) else None
        text = f"{metric_id}: {display_value}"
        if isinstance(unit, str) and unit and unit != "count":
            text = f"{text} {unit}"
        if isinstance(metric_status, str):
            text = f"{text} ({metric_status})"
        if isinstance(time_preset, str) and time_preset:
            text = f"{text}; preset={time_preset}"
        return {
            "metric_id": metric_id,
            "display_value": display_value,
            "metric_status": metric_status,
            "unit": unit,
            "time_preset": time_preset,
            "text": text,
        }

    def _build_text_for_prompt(self, prompt_projection: dict[str, Any]) -> str:
        parts: list[str] = []
        parts.append(f"[{prompt_projection['tool_name']}] {prompt_projection['status']}")
        if prompt_projection.get("summary"):
            parts.append(prompt_projection["summary"])
        if prompt_projection.get("safe_error"):
            parts.append(f"error: {prompt_projection['safe_error']['safe_message']}")
        text = " — ".join(parts)
        if len(text) > _MAX_TEXT_FOR_PROMPT:
            text = text[: _MAX_TEXT_FOR_PROMPT - 3] + "..."
        return text

    @staticmethod
    def _business_query_prompt_summary(normalized: dict[str, Any]) -> dict[str, Any] | None:
        business_query = normalized.get("business_query")
        if not isinstance(business_query, dict):
            return None
        text = business_query_response_text(business_query)
        return {
            "operation": business_query.get("operation"),
            "resource_label": business_query.get("resource_label"),
            "result_label": business_query.get("result_label"),
            "row_count": business_query.get("row_count"),
            "limit": business_query.get("limit"),
            "safe_reason": business_query.get("safe_reason"),
            "text": text,
        }

    # ------------------------------------------------------------------
    # Audit and resource refs
    # ------------------------------------------------------------------

    def _build_audit_refs(
        self,
        result: ToolResultV2,
        tool_call_id: str,
        policy_decision_ref: str | None,
    ) -> list[Any]:
        refs: list[Any] = []
        if result.audit_ref:
            refs.append(result.audit_ref)
        if policy_decision_ref:
            refs.append(policy_decision_ref)
        return refs

    def _build_resource_refs(self, result: ToolResultV2) -> list[Any]:
        return self._business_fact_refs_from_envelope(result)

    # ------------------------------------------------------------------
    # Debug projection
    # ------------------------------------------------------------------

    def _build_debug_projection(
        self,
        data: dict[str, Any],
        result: ToolResultV2,
    ) -> dict[str, Any]:
        return {
            "had_raw_data": bool(data),
            "redaction_applied": _has_raw_sentinels_in_dict(data),
            "business_fact_ref_count": len(result.business_fact_refs),
            "policy_evidence_ref_count": len(self._extract_policy_evidence_refs(data)),
            "status": result.status,
        }


def _has_raw_sentinels_in_dict(data: dict[str, Any]) -> bool:
    """Check whether raw sentinel keys are present at any nesting level."""
    for key, value in data.items():
        if key in _RAW_SENTINEL_KEYS:
            return True
        if isinstance(value, dict) and _has_raw_sentinels_in_dict(value):
            return True
    return False


def _looks_like_metric_result(data: dict[str, Any]) -> bool:
    if not _METRIC_RESULT_KEYS.issubset(data):
        return False
    return (
        isinstance(data.get("metric_id"), str)
        and isinstance(data.get("status"), str)
        and isinstance(data.get("unit"), str)
        and isinstance(data.get("display_value"), str)
    )


def _contains_sqlish_token(value: str) -> bool:
    upper = value.upper()
    return any(token in upper for token in ("SELECT ", " FROM ", " JOIN ", " WHERE ", "INSERT ", "UPDATE ", "DELETE "))

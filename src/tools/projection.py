"""Tool result projection into normalized, prompt, audit, and debug surfaces."""

from __future__ import annotations

from typing import Any

from src.tools.contracts import ToolResultProjectionV1, ToolResultV2

# Keys that must never appear in normalized or prompt surfaces.
_RAW_SENTINEL_KEYS: set[str] = {
    "raw",
    "raw_payload",
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
    "status",
    "source_system",
    "summary",
    "best_score",
    "retrieval_status",
}

# Typed ref keys extracted from result.data.
_BUSINESS_FACT_REF_KEYS: set[str] = {
    "order_no",
    "refund_case_no",
    "ticket_id",
    "tracking_no",
    "merchant_id",
}

_POLICY_EVIDENCE_REF_KEYS: set[str] = {
    "policy_id",
    "policy_version",
    "evidence_type",
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
        resource_refs = self._build_resource_refs(data, tool_call_id)
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

        # Typed refs.
        business_refs = self._extract_business_fact_refs(data)
        if business_refs:
            normalized["business_fact_refs"] = business_refs

        policy_refs = self._extract_policy_evidence_refs(data)
        if policy_refs:
            normalized["policy_evidence_refs"] = policy_refs

        # Refs from the ToolResultV2 envelope (not from data).
        if result.business_fact_refs:
            normalized["business_fact_refs"] = [
                {"resource_type": ref.resource_type, "resource_id": ref.resource_id}
                for ref in result.business_fact_refs
            ]
        if result.policy_evidence_refs:
            normalized["policy_evidence_refs"] = [
                {"evidence_id": ref.evidence_id, "doc_key": ref.doc_key}
                for ref in result.policy_evidence_refs
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

        # Case-memory items (sanitized).
        case_memory = data.get("_case_memory_items")
        if isinstance(case_memory, list):
            normalized["_case_memory_items"] = self._sanitize_case_memory(case_memory)

        return normalized

    def _extract_business_fact_refs(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for key in _BUSINESS_FACT_REF_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value:
                refs.append({"resource_type": key, "resource_id": value})
        return refs

    def _extract_policy_evidence_refs(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for key in _POLICY_EVIDENCE_REF_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value:
                refs.append({"ref_type": key, "ref_id": value})
        return refs

    def _sanitize_case_memory(self, items: list[Any]) -> list[dict[str, Any]]:
        sanitized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            safe_entry: dict[str, Any] = {}
            for key in ("case_id", "similarity", "snippet", "outcome"):
                if key in item:
                    value = item[key]
                    if isinstance(value, (str, int, float, bool)):
                        safe_entry[key] = value
            if safe_entry:
                sanitized.append(safe_entry)
        return sanitized

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

        return {
            "tool_name": tool_name,
            "status": result.status,
            "summary": normalized.get("summary", result.summary[:500]),
            "business_fact_refs": normalized.get("business_fact_refs", []),
            "policy_candidate_refs": normalized.get("policy_evidence_refs", []),
            "resource_refs": normalized.get("business_fact_refs", []),
            "warnings": warnings,
            "safe_error": safe_error,
            "redaction_applied": redaction_applied,
            "text_for_prompt": "",  # filled by _build_text_for_prompt
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
            text = text[:_MAX_TEXT_FOR_PROMPT - 3] + "..."
        return text

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

    def _build_resource_refs(
        self,
        data: dict[str, Any],
        tool_call_id: str,
    ) -> list[Any]:
        refs: list[Any] = []
        for key in _BUSINESS_FACT_REF_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value:
                refs.append({"resource_type": key, "resource_id": value})
        return refs

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
            "business_fact_ref_count": len(self._extract_business_fact_refs(data)),
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

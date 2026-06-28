from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal


TargetGraphKind = Literal["node", "router"]
TargetGraphStatus = Literal["runtime", "compatibility_alias", "deferred_non_runnable", "unknown_passthrough"]


@dataclass(frozen=True)
class GraphVocabularyEntry:
    legacy_name: str
    target_name: str
    kind: TargetGraphKind
    status: TargetGraphStatus
    runnable: bool
    reason_codes: tuple[str, ...] = ()


def _entry(
    legacy_name: str,
    target_name: str,
    kind: TargetGraphKind,
    status: TargetGraphStatus,
    runnable: bool,
    reason_codes: tuple[str, ...] = (),
) -> GraphVocabularyEntry:
    return GraphVocabularyEntry(
        legacy_name=legacy_name,
        target_name=target_name,
        kind=kind,
        status=status,
        runnable=runnable,
        reason_codes=reason_codes,
    )


_ENTRIES: tuple[GraphVocabularyEntry, ...] = (
    _entry("receive_request", "receive_request", "node", "runtime", True),
    _entry("investigate", "investigate", "node", "runtime", True),
    _entry("clarification_gate", "clarification_gate", "node", "runtime", True),
    _entry("approval_gate", "approval_gate", "node", "runtime", True),
    _entry("action_draft", "action_draft", "node", "runtime", True),
    _entry("final_response", "final_response", "node", "runtime", True),
    _entry("memory_write", "memory_write", "node", "runtime", True),
    _entry("classify_intent", "contextual_intent_resolve", "node", "compatibility_alias", True),
    _entry("intent_classification", "contextual_intent_resolve", "node", "compatibility_alias", True),
    _entry("contextual_intent_resolve", "contextual_intent_resolve", "node", "compatibility_alias", True),
    _entry("classify_intent:pre_route", "safety_pre_route", "node", "compatibility_alias", True),
    _entry("safety_pre_route", "safety_pre_route", "node", "compatibility_alias", True),
    _entry("session_memory_load", "session_context_load", "node", "compatibility_alias", True),
    _entry("session_context_load", "session_context_load", "node", "runtime", True),
    _entry("long_term_memory_retrieve", "memory_context_load", "node", "compatibility_alias", True),
    _entry("reviewed_memory_context_retrieve", "memory_context_load", "node", "runtime", True),
    _entry("memory_context_load", "memory_context_load", "node", "compatibility_alias", True),
    # alias: extract_slots -> slot_resolution_gate
    _entry(
        "extract_slots",
        "slot_resolution_gate",
        "node",
        "compatibility_alias",
        True,
        ("SLOT_RESOLUTION_GATE_PROJECTED_FROM_EXTRACT_SLOTS",),
    ),
    _entry(
        "slot_resolution_gate",
        "slot_resolution_gate",
        "node",
        "compatibility_alias",
        True,
        ("SLOT_RESOLUTION_GATE_PROJECTED_FROM_EXTRACT_SLOTS",),
    ),
    _entry(
        "rag_context_build",
        "rag_context_build",
        "node",
        "runtime",
        True,
    ),
    _entry(
        "claim_verify",
        "claim_verify",
        "node",
        "deferred_non_runnable",
        False,
        ("PHASE_33_APF_14_OWNED",),
    ),
    _entry("route_after_intent", "route_after_contextual_intent", "router", "compatibility_alias", True),
    _entry("route_after_contextual_intent", "route_after_contextual_intent", "router", "compatibility_alias", True),
    _entry("route_after_slots", "route_after_slot_resolution", "router", "compatibility_alias", True),
    _entry("route_after_slot_resolution", "route_after_slot_resolution", "router", "compatibility_alias", True),
)

_ENTRY_BY_KIND_AND_NAME = MappingProxyType({(entry.kind, entry.legacy_name): entry for entry in _ENTRIES})


def graph_vocabulary_entry(name: str, *, kind: TargetGraphKind | None = None) -> GraphVocabularyEntry | None:
    if kind is not None:
        return _ENTRY_BY_KIND_AND_NAME.get((kind, name))
    matches = [entry for entry in _ENTRIES if entry.legacy_name == name]
    if len(matches) == 1:
        return matches[0]
    return None


def target_graph_name(name: str, *, kind: TargetGraphKind | None = None) -> str:
    entry = graph_vocabulary_entry(name, kind=kind)
    if entry is None:
        return name
    return entry.target_name


def is_deferred_non_runnable_target(name: str, *, kind: TargetGraphKind | None = None) -> bool:
    entry = graph_vocabulary_entry(name, kind=kind)
    return bool(entry and entry.status == "deferred_non_runnable" and entry.runnable is False)


def project_trace_step_for_contract(step: Mapping[str, Any]) -> dict[str, Any]:
    implementation_node = str(step.get("node") or "unknown")
    entry = graph_vocabulary_entry(implementation_node, kind="node") or graph_vocabulary_entry(
        implementation_node, kind="router"
    )
    projected = dict(step)
    projected["implementation_node"] = implementation_node
    projected["target_node"] = implementation_node if entry is None else entry.target_name
    projected["target_graph_status"] = "unknown_passthrough" if entry is None else entry.status
    projected["target_graph_runnable"] = True if entry is None else entry.runnable
    return projected

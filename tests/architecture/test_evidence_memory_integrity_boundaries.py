from __future__ import annotations

import ast
import inspect
from pathlib import Path
import re

from src.knowledge.evidence_identity import ACCEPTED_POLICY_SCOPE_TYPE
from src.replay.service import ReplayService


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
EVIDENCE_OWNER = "src/knowledge/evidence_identity.py"
EVIDENCE_COMPATIBILITY_OWNERS = {
    EVIDENCE_OWNER,
    "src/knowledge/schemas.py",
}
MEMORY_IDENTITY_OWNER = "src/memory/identity.py"
APPROVAL_OWNER = "src/approvals/service.py"
REPLAY_OWNER = "src/replay/service.py"
PROMOTION_OWNER = "src/memory/fact_promotion.py"
PRECEDENT_OWNER = "src/memory/case_precedent.py"
CASE_MEMORY_OWNER = "src/memory/case_memory.py"
EMITTER_OWNERS = {
    "src/agent/events.py",
    "src/agent/nodes/investigate.py",
    "src/replay/decision_events.py",
}


def _function_nodes(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)]


def _argument_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
    return {argument.arg for argument in arguments}


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _node_source(source: str, node: ast.AST) -> str:
    return ast.get_source_segment(source, node) or ""


def find_integrity_boundary_violations(relative_path: str, source: str) -> frozenset[str]:
    """Return named Phase 64.2 ownership violations for one Python source."""

    tree = ast.parse(source, filename=relative_path)
    violations: set[str] = set()
    functions = _function_nodes(tree)

    if relative_path not in EVIDENCE_COMPATIBILITY_OWNERS:
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                rendered = _node_source(source, node)
                if "@v" in rendered and "/" in rendered:
                    violations.add("alias_outside_compatibility_owner")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node)
        keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg is not None}
        if call_name in {
            "mint_canonical_evidence_identity",
            "validate_canonical_evidence_identity",
            "resolve_evidence_identity",
            "resolve_exact",
            "resolve_legacy_alias",
        }:
            scope = keywords.get("expected_scope_type")
            if isinstance(scope, ast.Constant) and scope.value != "tenant_policy":
                violations.add("unsupported_policy_scope_invention")
        if call_name == "append_event":
            if "evidence_refs_json" in keywords:
                violations.add("legacy_append_input")
            typed = keywords.get("canonical_evidence_refs")
            if isinstance(typed, ast.List) and any(isinstance(item, ast.Dict) for item in typed.elts):
                violations.add("raw_canonical_ref_append")
        if call_name == "_build_replay_evidence_snapshots":
            containing = [fn for fn in functions if node in ast.walk(fn)]
            if relative_path != REPLAY_OWNER or not containing or containing[0].name != "append_event":
                violations.add("snapshot_builder_outside_append")
        if call_name == "CaseWorkingContextVerifiedFactV1" and relative_path != PROMOTION_OWNER:
            violations.add("verified_fact_outside_promotion_owner")
        if call_name == "canonical_hash" and relative_path != MEMORY_IDENTITY_OWNER and "/memory/" in relative_path:
            function = next((fn for fn in functions if node in ast.walk(fn)), None)
            if function is not None and any(term in function.name for term in ("candidate", "identity")):
                violations.add("local_memory_candidate_serializer")

    for function in functions:
        names = _argument_names(function)
        if function.name == "append_event" and "evidence_refs_json" in names:
            violations.add("legacy_append_parameter")
        if relative_path in EMITTER_OWNERS and "evidence_snapshot_refs" in names:
            violations.add("emitter_snapshot_input")

    if relative_path == APPROVAL_OWNER:
        for function in functions:
            if function.name not in {"create_request", "_prepare_replacement"}:
                continue
            body = _node_source(source, function)
            persistence_positions = [
                position
                for token in ("create_request_with_single_level", "_build_and_persist_snapshot")
                if (position := body.find(token)) >= 0
            ]
            validation_position = body.find("_validate_canonical_snapshot_evidence")
            if persistence_positions and (
                validation_position < 0 or validation_position > min(persistence_positions)
            ):
                violations.add("approval_persistence_without_recomputation")

    if relative_path == REPLAY_OWNER:
        if re.search(r"\bPolicyDocument\b|\bPolicyChunk\b", source):
            violations.add("historical_lookup_through_mutable_heads")
        if "Read-only adapter for evidence JSON" not in source or "resolve_persisted_legacy_event_evidence" not in source:
            violations.add("legacy_projection_not_read_only")

    if relative_path == PRECEDENT_OWNER:
        required = (
            "for fact in content.verified_facts",
            'memory_authority_class="contextual_only"',
            "source_authorities=source_authorities",
        )
        if any(token not in source for token in required):
            violations.add("source_memory_authority_conflation")
        if "content.evidence_refs" in source:
            violations.add("rejected_observation_copied_to_case_memory")

    if relative_path == CASE_MEMORY_OWNER:
        required = (
            "lock_owner_claim(",
            "expected_lifecycle_version",
            'claim.claim_state = "terminal"',
            "LegacyUnresolvedCaseMemoryProvenanceV1",
            "resolved_case_memory_provenance",
        )
        if any(token not in source for token in required):
            violations.add("review_or_terminal_lifecycle_without_claim_cas")
        if 'claim.claim_state == "active"' not in source or '"identity_conflict"' not in source:
            violations.add("active_index_used_as_resurrection_authority")

    return frozenset(violations)


def test_phase64_2_guards_reject_representative_pre_phase_patterns() -> None:
    representative_patterns = (
        (
            "src/agent/events.py",
            "async def emit(*, evidence_snapshot_refs=None): pass",
            "emitter_snapshot_input",
        ),
        (
            "src/replay/service.py",
            "class X:\n async def append_event(self, *, evidence_refs_json=None): pass",
            "legacy_append_parameter",
        ),
        (
            "src/replay/lifecycle.py",
            "async def emit(service): await service.append_event(evidence_refs_json=[{}])",
            "legacy_append_input",
        ),
        (
            "src/replay/lifecycle.py",
            "async def emit(service): await service.append_event(canonical_evidence_refs=[{'evidence_id': 'x'}])",
            "raw_canonical_ref_append",
        ),
        (
            "src/replay/lifecycle.py",
            "async def emit(service): await service._build_replay_evidence_snapshots()",
            "snapshot_builder_outside_append",
        ),
        (
            "src/knowledge/retrieval.py",
            "def alias(doc, chunk, version): return f'{doc}/{chunk}@v{version}'",
            "alias_outside_compatibility_owner",
        ),
        (
            "src/knowledge/retrieval.py",
            "resolve_exact(expected_scope_type='merchant_policy')",
            "unsupported_policy_scope_invention",
        ),
        (
            "src/memory/local.py",
            "def build_candidate_identity(value): return canonical_hash(value)",
            "local_memory_candidate_serializer",
        ),
        (
            "src/memory/case_working_context_lifecycle.py",
            "def project(): return CaseWorkingContextVerifiedFactV1(text='summary only')",
            "verified_fact_outside_promotion_owner",
        ),
        (
            "src/memory/case_precedent.py",
            "def project(content): return content.evidence_refs",
            "rejected_observation_copied_to_case_memory",
        ),
        (
            "src/memory/case_memory.py",
            "async def approve(memory): memory.review_status = 'approved'",
            "review_or_terminal_lifecycle_without_claim_cas",
        ),
    )
    for path, source, expected in representative_patterns:
        assert expected in find_integrity_boundary_violations(path, source), (path, expected)


def test_phase64_2_canonical_owners_pass_boundary_guards() -> None:
    owners = (
        EVIDENCE_OWNER,
        "src/repositories/evidence_version_repo.py",
        APPROVAL_OWNER,
        REPLAY_OWNER,
        MEMORY_IDENTITY_OWNER,
        "src/memory/case_working_context_lifecycle.py",
        PROMOTION_OWNER,
        PRECEDENT_OWNER,
        CASE_MEMORY_OWNER,
    )
    violations = {
        path: find_integrity_boundary_violations(path, (ROOT / path).read_text(encoding="utf-8"))
        for path in owners
    }

    assert violations == {path: frozenset() for path in owners}


def test_phase64_2_repository_has_no_forbidden_owner_drift() -> None:
    violations: dict[str, frozenset[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        relative = str(path.relative_to(ROOT))
        found = find_integrity_boundary_violations(relative, path.read_text(encoding="utf-8"))
        if found:
            violations[relative] = found
    assert violations == {}


def test_replay_append_signature_is_typed_only_and_snapshot_build_is_append_owned() -> None:
    parameters = inspect.signature(ReplayService.append_event).parameters
    assert "canonical_evidence_refs" in parameters
    assert "evidence_refs_json" not in parameters
    assert parameters["canonical_evidence_refs"].annotation == "list[EvidenceRefV1] | None"
    assert ACCEPTED_POLICY_SCOPE_TYPE == "tenant_policy"


def test_phase64_2_contract_owners_keep_exact_scope_and_separate_authority() -> None:
    evidence = (ROOT / EVIDENCE_OWNER).read_text(encoding="utf-8")
    repository = (ROOT / "src/repositories/evidence_version_repo.py").read_text(encoding="utf-8")
    promotion = (ROOT / PROMOTION_OWNER).read_text(encoding="utf-8")
    provenance = (ROOT / "src/memory/schemas.py").read_text(encoding="utf-8")
    case_memory = (ROOT / CASE_MEMORY_OWNER).read_text(encoding="utf-8")

    assert 'ACCEPTED_POLICY_SCOPE_TYPE = "tenant_policy"' in evidence
    assert "expected_scope_id=str(tenant_id)" in repository
    assert 'candidate.authority_class == "contextual_only"' in promotion
    assert 'candidate.authority_class == "unknown"' in promotion
    assert 'memory_authority_class: Literal["contextual_only"]' in provenance
    assert "LegacyUnresolvedCaseMemoryProvenanceV1" in provenance
    assert "CaseMemoryIdentityClaim" in case_memory

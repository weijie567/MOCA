from __future__ import annotations

import ast
from copy import deepcopy
import inspect
from pathlib import Path
import re

import yaml

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
PHASE_DIR = ROOT / ".planning" / "phases" / "64.2-evidence-identity-immutable-replay-and-memory-provenance"
PLAN_09_PATH = PHASE_DIR / "64.2-09-PLAN.md"
CONTRACT_PATH = ROOT / "docs" / "contract-spec.md"
DEBT_PATH = ROOT / ".planning" / "ARCHITECTURE-DEBT.md"


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
    cwc_lifecycle = (ROOT / "src/memory/case_working_context_lifecycle.py").read_text(encoding="utf-8")
    provenance = (ROOT / "src/memory/schemas.py").read_text(encoding="utf-8")
    case_memory = (ROOT / CASE_MEMORY_OWNER).read_text(encoding="utf-8")

    assert 'ACCEPTED_POLICY_SCOPE_TYPE = "tenant_policy"' in evidence
    assert "expected_scope_id=str(tenant_id)" in repository
    assert 'candidate.authority_class == "contextual_only"' in promotion
    assert 'candidate.authority_class == "unknown"' in promotion
    assert "resolve_policy_evidence_ref_exact" in cwc_lifecycle
    assert "EvidenceVersionRepository(session).resolve_immutable_evidence" in cwc_lifecycle
    assert "_validated_policy_evidence_ids" in cwc_lifecycle
    assert 'memory_authority_class: Literal["contextual_only"]' in provenance
    assert "LegacyUnresolvedCaseMemoryProvenanceV1" in provenance
    assert "CaseMemoryIdentityClaim" in case_memory


def _section(source: str, heading: str, next_heading: str) -> str:
    start = source.index(heading)
    end = source.index(next_heading, start + len(heading))
    return source[start:end]


def _load_phase_plan_frontmatters() -> dict[str, dict]:
    paths = sorted(PHASE_DIR.glob("64.2-??-PLAN.md"))
    expected_names = [f"64.2-{number:02d}-PLAN.md" for number in range(1, 12)]
    assert [path.name for path in paths] == expected_names
    plans: dict[str, dict] = {}
    for path in paths:
        source = path.read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(source.split("---", 2)[1])
        plan_id = f"64.2-{frontmatter['plan']}"
        assert path.name == f"{plan_id}-PLAN.md"
        assert plan_id not in plans
        plans[plan_id] = frontmatter
    return plans


def _plan_graph_violations(plans: dict[str, dict]) -> frozenset[str]:
    violations: set[str] = set()
    for plan_id, plan in plans.items():
        for dependency in plan.get("depends_on", []):
            if dependency not in plans:
                violations.add("missing_dependency")
            elif plans[dependency]["wave"] >= plan["wave"]:
                violations.add("wave_inversion")

    def reachable(start: str, target: str) -> bool:
        seen: set[str] = set()
        stack = list(plans[start].get("depends_on", []))
        while stack:
            current = stack.pop()
            if current == target:
                return True
            if current in seen or current not in plans:
                continue
            seen.add(current)
            stack.extend(plans[current].get("depends_on", []))
        return False

    if any(reachable(plan_id, plan_id) for plan_id in plans):
        violations.add("dependency_cycle")

    plan_ids = sorted(plans)
    for index, left_id in enumerate(plan_ids):
        left = plans[left_id]
        left_files = set(left.get("files_modified", [])) | set(left.get("conditional_files_modified", []))
        for right_id in plan_ids[index + 1 :]:
            right = plans[right_id]
            right_files = set(right.get("files_modified", [])) | set(
                right.get("conditional_files_modified", [])
            )
            if not left_files.intersection(right_files):
                continue
            if left["wave"] == right["wave"]:
                violations.add("same_wave_shared_file")
            if not reachable(left_id, right_id) and not reachable(right_id, left_id):
                violations.add("unordered_shared_file")
    return frozenset(violations)


def test_phase64_2_contract_sections_have_distinct_implemented_markers() -> None:
    source = CONTRACT_PATH.read_text(encoding="utf-8")
    evidence = _section(source, "### 8.3 Knowledge / RAG (normative)", "### 8.4 Business Tools (normative)")
    memory = _section(source, "## 13. Memory 设计", "## 14. Prompt 设计")
    replay = _section(source, "## 17. Observability / Replay 设计", "## 18. 数据模型建议")

    for marker in (
        "phase64.2-evidence-identity:implemented",
        "evidence_identity.v1",
        'scope_type="tenant_policy"',
        "scope_id=str(tenant_id)",
        "immutable document/chunk IDs",
        "shared rollout lock",
        "CAS epoch",
        "rollout -> document head -> chunk heads",
        "exactly one ingestion sequence",
        "approval repository validation",
        "compatibility-read-only",
        "025 -> deploy/health/dual-write -> 026",
        "disable reads; keep dual-write active; quarantine; reconcile; CAS re-enable",
    ):
        assert marker in evidence

    for marker in (
        "phase64.2-memory-provenance:implemented",
        "nfkc_casefold_legacy",
        "nfc_selective_v2",
        "single identity owner",
        "business_fact/policy_evidence-only promotion",
        "rejected-observation exclusion",
        "per-source authority",
        "memory_authority_class=contextual_only",
        "LegacyUnresolvedCaseMemoryProvenanceV1",
        "durable terminal claims",
        "multi-valued lineage",
    ):
        assert marker in memory

    for marker in (
        "phase64.2-replay-binding:implemented",
        "canonical_evidence_refs",
        "only new append input",
        "no evidence_refs_json append parameter",
        "append_event-only snapshot builder",
        "full snapshot equality",
        "exact retained immutable resolution",
        "lifecycle visibility",
        "dependency-protected tombstone retention",
        "persisted-legacy/read-adapter-only unresolved",
    ):
        assert marker in replay


def test_phase64_2_rag_and_memory_ledgers_are_distinct_and_evidence_backed() -> None:
    source = DEBT_PATH.read_text(encoding="utf-8")
    rag = _section(source, "# 3. RAG（检索 / 证据 / 上下文构建）", "# 4. 记忆（Memory）")
    memory = source[source.index("# 4. 记忆（Memory）") :]
    required_common = ("✅已修复验证", "64.2-09", "legacy risk", "target/defer")

    assert "phase64.2-rag-integrity:implemented" in rag
    assert "tests/integration/test_phase64_2_integrity_matrix.py" in rag
    assert "tests/architecture/test_evidence_memory_integrity_boundaries.py" in rag
    assert all(marker in rag for marker in required_common)
    assert "phase64.2-memory-integrity:implemented" in memory
    assert "tests/integration/test_phase64_2_integrity_matrix.py" in memory
    assert "tests/architecture/test_evidence_memory_integrity_boundaries.py" in memory
    assert all(marker in memory for marker in required_common)


def test_phase64_2_decision_coverage_and_key_links_are_complete() -> None:
    source = PLAN_09_PATH.read_text(encoding="utf-8")
    table = source.split("<decision_coverage>", 1)[1].split("</decision_coverage>", 1)[0]
    rows = re.findall(r"^\| (D-\d{2}) \| ([^|]+) \| ([^|]+) \|$", table, flags=re.MULTILINE)
    decisions = [row[0] for row in rows]

    assert decisions == [f"D-{number:02d}" for number in range(1, 21)]
    assert len(decisions) == len(set(decisions))
    for _decision, owners, rationale in rows:
        task_ids = re.findall(r"64\.2-(\d{2})-(\d{2})", owners)
        assert task_ids
        assert all(1 <= int(plan) <= 9 and int(task) >= 1 for plan, task in task_ids)
        assert rationale.strip()

    plan_09 = _load_phase_plan_frontmatters()["64.2-09"]
    key_links = plan_09["must_haves"]["key_links"]
    assert len(key_links) == 2
    assert all({"from", "to", "via", "pattern"} <= link.keys() for link in key_links)
    assert all(all(str(link[key]).strip() for key in ("from", "to", "via", "pattern")) for link in key_links)


def test_phase64_2_plan_graph_is_exact_acyclic_and_shared_file_ordered() -> None:
    plans = _load_phase_plan_frontmatters()

    assert set(plans) == {f"64.2-{number:02d}" for number in range(1, 12)}
    assert _plan_graph_violations(plans) == frozenset()


def test_phase64_2_plan_graph_guard_rejects_structural_mutations() -> None:
    plans = _load_phase_plan_frontmatters()

    missing = deepcopy(plans)
    missing["64.2-09"]["depends_on"].append("64.2-99")
    assert "missing_dependency" in _plan_graph_violations(missing)

    cycle = deepcopy(plans)
    cycle["64.2-01"]["depends_on"] = ["64.2-09"]
    assert "dependency_cycle" in _plan_graph_violations(cycle)

    inverted = deepcopy(plans)
    inverted["64.2-09"]["wave"] = 3
    assert "wave_inversion" in _plan_graph_violations(inverted)

    same_wave = deepcopy(plans)
    same_wave["64.2-09"]["wave"] = 5
    same_wave["64.2-09"]["files_modified"].append("src/memory/case_memory.py")
    assert "same_wave_shared_file" in _plan_graph_violations(same_wave)

    unordered = deepcopy(plans)
    unordered["64.2-09"]["depends_on"] = []
    unordered["64.2-09"]["files_modified"].append("src/memory/case_memory.py")
    assert "unordered_shared_file" in _plan_graph_violations(unordered)

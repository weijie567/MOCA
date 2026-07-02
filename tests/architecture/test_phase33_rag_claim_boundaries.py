from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from src.agent import graph_vocabulary
from src.agent.rag_claim_summary import sanitize_rag_claim_payload
from src.agent.routing import RAG_CONTEXT_STATUSES, route_after_claim_verify, route_after_rag_context


ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = ROOT / "src" / "agent" / "graph.py"
GRAPH_VOCABULARY_PATH = ROOT / "src" / "agent" / "graph_vocabulary.py"
ROUTING_PATH = ROOT / "src" / "agent" / "routing.py"
RAG_NODE_PATH = ROOT / "src" / "agent" / "nodes" / "rag_context_build.py"
CLAIM_NODE_PATH = ROOT / "src" / "agent" / "nodes" / "claim_verify.py"
RECOMMENDATION_NODE_PATH = ROOT / "src" / "agent" / "nodes" / "generate_recommendation.py"
SUMMARY_PROJECTION_PATH = ROOT / "src" / "agent" / "rag_claim_summary.py"
PHASE33_DIR = ROOT / ".planning" / "phases" / "33-rag-context-build-and-claim-verification"

RAG_WRITER_KEYS = {
    "rag_context_status",
    "verified_evidence_package",
    "citation_map",
    "evidence_map",
}
CLAIM_WRITER_KEYS = {
    "claim_verification_bundle",
    "blocked_claims",
    "safe_support_refs",
}
APPROVED_PHASE33_SUMMARY_KEYS = {
    "schema_version",
    "rag_context_status",
    "verified_evidence_count",
    "rejected_candidate_count",
    "stale_ref_count",
    "conflict_ref_count",
    "claim_verification_status",
    "blocked_claim_count",
    "safe_support_ref_count",
}
ROUTER_FORBIDDEN_SNIPPETS = (
    "ChatOpenAI",
    "PolicyKnowledgeService",
    "PolicyRetrievalEngine",
    "BusinessToolService",
    "ToolPlatform",
    "Repository",
    "requests.",
    "httpx",
    "session.execute",
    ".execute(",
    ".search(",
    ".invoke(",
    "await ",
)
NODE_REPOSITORY_BYPASS_PREFIXES = (
    "src.repositories",
    "src.knowledge.repository",
    "src.knowledge.repositories",
)
PHASE33_ARTIFACT_GLOBS = (
    "33-*-PLAN.md",
    "33-*-SUMMARY.md",
    "33-VALIDATION.md",
    "33-RAG-CLAIM-TARGET-MAPPING.md",
)
BULLET_INLINE_COMMAND_RE = re.compile(r"^-\s+`([^`]+)`")


def test_runtime_graph_registers_rag_context_build_and_claim_verify_nodes() -> None:
    graph_source = _source(GRAPH_PATH)

    assert 'builder.add_node("rag_context_build", rag_context_build)' in graph_source
    assert 'builder.add_node("claim_verify", claim_verify)' in graph_source
    assert "route_after_rag_context" in graph_source
    assert "route_after_claim_verify" in graph_source
    assert '"rag_context_build": "rag_context_build"' in graph_source
    assert '"claim_verify": "claim_verify"' in graph_source


def test_graph_vocabulary_marks_rag_claim_targets_runtime_runnable() -> None:
    vocabulary_source = _source(GRAPH_VOCABULARY_PATH)

    for name in ("rag_context_build", "claim_verify"):
        entry = graph_vocabulary.graph_vocabulary_entry(name, kind="node")

        assert entry is not None
        assert entry.target_name == name
        assert entry.status == "runtime"
        assert entry.runnable is True
        assert graph_vocabulary.is_deferred_non_runnable_target(name, kind="node") is False
        assert f'"{name}"' in vocabulary_source


def test_rag_and_claim_routers_are_total_and_side_effect_free() -> None:
    assert RAG_CONTEXT_STATUSES == {
        "not_required",
        "verified",
        "partial",
        "no_evidence",
        "unauthorized",
        "stale",
        "conflict",
        "invalid_hash",
        "invalid_scope",
        "build_error",
    }

    rag_routes = {
        route_after_rag_context(
            {
                "rag_context_status": status,
                "evidence_policy": {"evidence_required": status != "not_required"},
                "primary_intent": "policy_qa",
                "requested_operation": "advise",
            }
        )
        for status in RAG_CONTEXT_STATUSES
    }
    claim_routes = {
        route_after_claim_verify({}),
        route_after_claim_verify({"blocked_claims": ["claim-1"]}),
        route_after_claim_verify(
            {
                "claim_verification_bundle": {
                    "overall_status": "verified",
                    "route": "continue",
                    "claim_results": [],
                    "blocked_claims": [],
                    "safe_support_refs": [],
                },
                "proposed_action": {"action_type": "issue_coupon"},
            }
        ),
    }

    assert rag_routes <= {"recommendation_generation", "clarification_gate", "final_response"}
    assert claim_routes <= {"assess_risk_and_approval", "final_response"}

    router_source = "\n".join(
        [
            _function_source(ROUTING_PATH, "route_after_rag_context"),
            _function_source(ROUTING_PATH, "_route_after_rag_context"),
            _function_source(ROUTING_PATH, "route_after_claim_verify"),
            _function_source(ROUTING_PATH, "_route_after_claim_verify"),
        ]
    )
    for forbidden in ROUTER_FORBIDDEN_SNIPPETS:
        assert forbidden not in router_source


def test_writer_ownership_is_limited_to_phase33_target_fields() -> None:
    rag_keys = _literal_dict_keys(RAG_NODE_PATH)
    claim_keys = _literal_dict_keys(CLAIM_NODE_PATH)
    recommendation_keys = _literal_dict_keys(RECOMMENDATION_NODE_PATH)

    assert RAG_WRITER_KEYS <= rag_keys
    assert CLAIM_WRITER_KEYS.isdisjoint(rag_keys)
    assert CLAIM_WRITER_KEYS <= claim_keys
    assert RAG_WRITER_KEYS.isdisjoint(claim_keys)
    assert "material_claims" in recommendation_keys
    assert (RAG_WRITER_KEYS | CLAIM_WRITER_KEYS).isdisjoint(recommendation_keys)


def test_rag_claim_nodes_do_not_bypass_repositories_or_raw_database_access() -> None:
    violations: list[tuple[str, str]] = []
    for path in (RAG_NODE_PATH, CLAIM_NODE_PATH, RECOMMENDATION_NODE_PATH):
        imports = _import_targets(path)
        for module in imports:
            if module.startswith(NODE_REPOSITORY_BYPASS_PREFIXES):
                violations.append((str(path.relative_to(ROOT)), module))

        source = _source(path)
        for forbidden in ("session.execute", ".execute(", "select(", "insert(", "update(", "delete("):
            if forbidden in source:
                violations.append((str(path.relative_to(ROOT)), forbidden))

    assert violations == []


def test_rag_claim_safe_summary_strips_raw_package_and_verifier_projection_fields() -> None:
    source = _source(SUMMARY_PROJECTION_PATH)
    for forbidden_key in (
        "verified_evidence_package",
        "claim_verification_bundle",
        "debug_projection",
        "verifier_projection",
        "raw_semantic",
        "source_block",
        "ocr",
        "candidate_refs",
    ):
        assert f'"{forbidden_key}"' in source

    payload = {
        "verified_evidence_package": {
            "status": "verified",
            "evidence_map": {
                "policy_refund_timeout/chunk_001@v3": {
                    "evidence_id": "policy_refund_timeout/chunk_001@v3"
                }
            },
            "rejected_candidate_refs": [{"evidence_id": "candidate-only"}],
            "debug_projection": {"raw": "DEBUG_PROJECTION_SHOULD_NOT_LEAK"},
            "verifier_projection": {"prompt": "VERIFIER_PROJECTION_SHOULD_NOT_LEAK"},
        },
        "claim_verification_bundle": {
            "overall_status": "verified",
            "route": "continue",
            "safe_support_refs": [{"evidence_id": "policy_refund_timeout/chunk_001@v3"}],
            "blocked_claims": [],
        },
        "material_claims": [{"claim_id": "claim-1"}],
        "debug_projection": {"raw": "TOP_LEVEL_DEBUG_SHOULD_NOT_LEAK"},
        "verifier_projection": {"prompt": "TOP_LEVEL_VERIFIER_SHOULD_NOT_LEAK"},
        "raw_semantic": {"private": "RAW_SEMANTIC_SHOULD_NOT_LEAK"},
        "ocr_metadata_json": {"bbox": "OCR_SHOULD_NOT_LEAK"},
    }

    sanitized = sanitize_rag_claim_payload(payload)
    serialized = json.dumps(sanitized, ensure_ascii=False, sort_keys=True)

    assert set(sanitized["rag_claim_summary"]) == APPROVED_PHASE33_SUMMARY_KEYS
    assert sanitized["rag_claim_summary"]["verified_evidence_count"] == 1
    assert sanitized["rag_claim_summary"]["safe_support_ref_count"] == 1
    for forbidden in (
        "verified_evidence_package",
        "claim_verification_bundle",
        "debug_projection",
        "verifier_projection",
        "RAW_SEMANTIC_SHOULD_NOT_LEAK",
        "OCR_SHOULD_NOT_LEAK",
        "candidate-only",
    ):
        assert forbidden not in serialized


def test_phase33_artifacts_use_project_test_entrypoints_for_validation_commands() -> None:
    violations: list[str] = []
    for path in _phase33_artifacts():
        for line_number, command in _validation_commands(path):
            if command.startswith("pytest") or command.startswith("python -m pytest"):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {command}")

    assert violations == []


def _source(path: Path) -> str:
    return path.read_text()


def _literal_dict_keys(path: Path) -> set[str]:
    tree = ast.parse(_source(path))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def _function_source(path: Path, function_name: str) -> str:
    tree = ast.parse(_source(path))
    lines = _source(path).splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == function_name:
            assert node.end_lineno is not None
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"Function not found: {function_name}")


def _import_targets(path: Path) -> list[str]:
    tree = ast.parse(_source(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
            imports.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def _phase33_artifacts() -> list[Path]:
    artifacts: list[Path] = []
    for pattern in PHASE33_ARTIFACT_GLOBS:
        artifacts.extend(PHASE33_DIR.glob(pattern))
    return sorted(path for path in artifacts if path.exists())


def _validation_commands(path: Path) -> list[tuple[int, str]]:
    commands: list[tuple[int, str]] = []
    in_bash_block = False
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_bash_block = stripped in {"```bash", "```sh", "```shell"}
            continue
        command = ""
        if stripped.startswith("<automated>"):
            command = stripped.removeprefix("<automated>").split("</automated>", 1)[0].strip()
        elif in_bash_block:
            command = stripped.removeprefix("$ ").strip()
        elif match := BULLET_INLINE_COMMAND_RE.match(stripped):
            command = match.group(1).strip()
        elif stripped.startswith("| `"):
            command = stripped.strip("|").split("|", 1)[0].strip().strip("`")
        if command:
            commands.append((line_number, command))
    return commands

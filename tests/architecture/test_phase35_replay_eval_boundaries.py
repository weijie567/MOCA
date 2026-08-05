from __future__ import annotations

import ast
import json
from pathlib import Path

from src.replay.phase35_eval_manifest import REQUIRED_FORBIDDEN_BEHAVIOR_CASE_IDS


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
REPLAY_ROOT = SRC_ROOT / "replay"
TRACE_REPLAY_API_PATH = SRC_ROOT / "api" / "routers" / "traces.py"
DEV_CONTRACT_MANIFEST = ROOT / "eval" / "replay" / "dev-contract-manifest.v1.json"
PHASE35_EVAL_DOC = ROOT / "docs" / "quality" / "evaluation.md"
PHASE35_REPLAY_ARTIFACT_ROOT = ROOT / "eval" / "replay"

REPLAY_BY_RERUN_FORBIDDEN_STRINGS = (
    "invoke_graph",
    "with_structured_output",
    "ToolRuntime.invoke",
    "PolicyKnowledgeService.search",
    "build_verified_context",
    "verify_claims",
    "create_coupon_grant_draft",
    "create_draft",
)
PARALLEL_EVENT_ENVELOPE_CLASS_NAMES = {
    "DecisionEventEnvelopeV2",
    "ReplayDecisionEnvelope",
    "ParallelReplayEnvelope",
    "ServiceEventEnvelope",
}
REPLAY_ENVELOPE_ALLOWED_MODULES = {
    SRC_ROOT / "replay" / "decision_events.py",
    SRC_ROOT / "replay" / "service.py",
}
REAL_EXECUTION_SURFACE_NAMES = (
    "action_executions",
    "action_outbox_events",
    "action_reconciliation_jobs",
    "action_compensation_records",
    "ExternalExecutionWorker",
    "OutboxDispatcher",
    "ReconciliationWorker",
    "CompensationWorker",
)
PHYSICAL_MICROSERVICE_MARKERS = (
    "docker-compose.replay-service.yml",
    "k8s/replay",
    "service_mesh",
)
ALLOWED_FORBIDDEN_BEHAVIOR_TEST_ROOTS = (
    "tests/replay/",
    "tests/eval/",
    "tests/architecture/",
    "tests/agent/",
    "tests/actions/",
)


def test_replay_by_rerun_static_guard_is_scoped_to_replay_owned_code() -> None:
    replay_by_rerun_sources = [*sorted(REPLAY_ROOT.glob("*.py")), TRACE_REPLAY_API_PATH]
    violations: list[str] = []

    service_source = _source(SRC_ROOT / "replay" / "service.py")
    assert "async def get_replay" in service_source
    assert "AgentTraceEvent" in service_source

    for path in replay_by_rerun_sources:
        source = _source(path)
        for forbidden in REPLAY_BY_RERUN_FORBIDDEN_STRINGS:
            if forbidden in source:
                violations.append(f"{path.relative_to(ROOT)}: replay_by_rerun forbidden call {forbidden}")

    assert violations == []


def test_production_code_does_not_define_parallel_replay_event_envelopes() -> None:
    violations: list[str] = []

    for path in _production_python_paths():
        tree = ast.parse(_source(path), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name not in PARALLEL_EVENT_ENVELOPE_CLASS_NAMES:
                continue
            if path not in REPLAY_ENVELOPE_ALLOWED_MODULES:
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:class {node.name}")

    assert violations == []


def test_production_code_does_not_introduce_real_external_execution_surfaces() -> None:
    violations: list[str] = []

    for path in _production_python_paths():
        source = _source(path)
        for forbidden in REAL_EXECUTION_SURFACE_NAMES:
            if forbidden in source:
                violations.append(f"{path.relative_to(ROOT)}: forbidden real execution surface {forbidden}")

    assert violations == []


def test_phase35_docs_and_artifacts_do_not_introduce_physical_microservice_deployment() -> None:
    assert not (ROOT / "docker-compose.replay-service.yml").exists()
    assert not (ROOT / "k8s" / "replay").exists()

    violations: list[str] = []
    docs_and_artifacts = [PHASE35_EVAL_DOC, *sorted(PHASE35_REPLAY_ARTIFACT_ROOT.glob("*.json"))]
    for path in docs_and_artifacts:
        source = _source(path)
        for marker in PHYSICAL_MICROSERVICE_MARKERS:
            if marker in source:
                violations.append(f"{path.relative_to(ROOT)}: physical deployment marker {marker}")

    assert violations == []


def test_dev_contract_manifest_forbidden_behaviors_reference_concrete_tests() -> None:
    manifest = json.loads(DEV_CONTRACT_MANIFEST.read_text(encoding="utf-8"))
    cases = {case["case_id"]: case for case in manifest["forbidden_behaviors"]}

    assert set(cases) == REQUIRED_FORBIDDEN_BEHAVIOR_CASE_IDS
    assert "approval_payload_hash_mismatch_creates_action_draft" in cases

    missing_concrete_tests: list[str] = []
    for case_id, case in cases.items():
        test_paths = case.get("test_paths", [])
        concrete_paths = [
            test_path
            for test_path in test_paths
            if test_path.startswith(ALLOWED_FORBIDDEN_BEHAVIOR_TEST_ROOTS) and (ROOT / test_path).exists()
        ]
        if not concrete_paths:
            missing_concrete_tests.append(case_id)
        if {"D-13", "D-18"} & set(case.get("source_decisions", [])):
            assert case["gate_level"] == "dev-contract"
            assert case["blocking"] is True

    assert missing_concrete_tests == []


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _production_python_paths() -> list[Path]:
    return [
        path
        for path in sorted(SRC_ROOT.rglob("*.py"))
        if "__pycache__" not in path.parts and path.name != "__init__.py"
    ]

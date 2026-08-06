from __future__ import annotations

from pathlib import Path

from src.agent.graph_vocabulary import graph_vocabulary_entry, project_trace_step_for_contract, target_graph_name

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "architecture" / "memory.md"
MEMORY_AUTHORITY_TEST_PATH = ROOT / "tests" / "agent" / "test_memory_evidence_boundary.py"
REQUIRED_SLOTS_TEST_PATH = ROOT / "tests" / "agent" / "test_required_slots.py"
LONG_TERM_TEST_PATH = ROOT / "tests" / "memory" / "test_long_term_memory_service.py"
CASE_MEMORY_TEST_PATH = ROOT / "tests" / "memory" / "test_case_memory_retrieval.py"
TOMBSTONE_TEST_PATH = ROOT / "tests" / "memory" / "test_memory_tombstones.py"
MEMORY_POLICY_TEST_PATH = ROOT / "tests" / "memory" / "test_memory_policy.py"
SESSION_MEMORY_SERVICE_TEST_PATH = ROOT / "tests" / "memory" / "test_session_memory_service.py"
MEMORY_WRITE_SERVICE_TEST_PATH = ROOT / "tests" / "memory" / "test_memory_write_service.py"
MEMORY_CONTEXT_BUNDLE_TEST_PATH = ROOT / "tests" / "memory" / "test_memory_context_bundle.py"
MEMORY_POLICY_PATH = ROOT / "src" / "memory" / "policy.py"
MEMORY_WRITE_SERVICE_PATH = ROOT / "src" / "memory" / "write_service.py"
SESSION_MEMORY_SERVICE_PATH = ROOT / "src" / "memory" / "service.py"
SESSION_MEMORY_REPOSITORY_PATH = ROOT / "src" / "memory" / "repository.py"
MEMORY_CONTEXT_REFS_PATH = ROOT / "src" / "memory" / "context_refs.py"
MEMORY_WRITE_AUDIT_MIGRATION_PATH = (
    ROOT / "src" / "db" / "migrations" / "versions" / "020_memory_write_event_policy_audit.py"
)
LONG_TERM_REPOSITORY_PATH = ROOT / "src" / "memory" / "repository.py"
CASE_MEMORY_PATH = ROOT / "src" / "memory" / "case_memory.py"
MEMORY_REVIEW_API_PATH = ROOT / "src" / "api" / "routers" / "memory.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_memory_architecture_doc_locks_current_layers_and_vocabulary() -> None:
    source = _source(DOC_PATH)

    for term in (
        "SessionMemory",
        "session_memories",
        "SessionContextMemory",
        "memory_context_load",
        "memory_write",
        "MemoryContextBundle",
        "Case Working Context",
        "contextual_only",
    ):
        assert term in source

    for heading in (
        "## AgentState 与 checkpoint",
        "## Session context、bundle 与 thread summary",
        "## Case Working Context（CWC）",
        "## 长期偏好与已审案例先例",
        "## 当前实现限制",
    ):
        assert heading in source


def test_memory_architecture_doc_locks_authority_and_policy_boundaries() -> None:
    source = _source(DOC_PATH)

    for term in (
        "EvidenceRefV1",
        "BusinessFactRefV1",
        "ReplayEventV3",
        "contextual_only",
        "explicit_user_preference",
        "explicit_admin_preference",
        "semantic_episode_candidate",
        "llm_candidate",
        "tombstone",
        "needs_review",
    ):
        assert term in source


def test_memory_architecture_doc_rejects_broad_long_term_target_semantics() -> None:
    source = _source(DOC_PATH)

    for rejected in (
        "durable_profile_fact",
        "merchant_pattern",
        "operational_constraint",
        "deterministic durable tool results can auto-publish",
        "只有 durable 且不是当前业务对象状态时可 auto publish",
    ):
        assert rejected not in source

    assert "当前真正接通的长期偏好写入主路径只有管理员 API" in source
    assert "不能替代当前业务事实、政策证据、审批决定、动作授权、动作结果、审计事实或 replay truth" in source


def test_memory_architecture_doc_matches_landed_facades_and_rules() -> None:
    delta = _source(DOC_PATH)
    policy_source = _source(MEMORY_POLICY_PATH)
    write_service_source = _source(MEMORY_WRITE_SERVICE_PATH)
    session_memory_service_source = _source(SESSION_MEMORY_SERVICE_PATH)
    session_memory_repository_source = _source(SESSION_MEMORY_REPOSITORY_PATH)
    context_refs_source = _source(MEMORY_CONTEXT_REFS_PATH)
    audit_migration_source = _source(MEMORY_WRITE_AUDIT_MIGRATION_PATH)
    long_term_repository_source = _source(LONG_TERM_REPOSITORY_PATH)
    case_memory_source = _source(CASE_MEMORY_PATH)
    review_api_source = _source(MEMORY_REVIEW_API_PATH)

    assert "src/memory/policy.py" in delta
    assert "src/memory/write_service.py" in delta
    assert "src/api/routers/memory.py" in delta
    assert "MemoryContextBundle" in delta
    assert "class MemoryPolicyDecision" in policy_source
    assert "def long_term_memory_policy_decision" in policy_source
    assert "policy_version" in policy_source
    assert "blocked_by" in policy_source
    assert "def long_term_review_status_for_source" in policy_source
    assert "def case_memory_review_status_for_source" in policy_source
    assert "class MemoryWriteService" in write_service_source
    assert "def propose_candidates" in write_service_source
    assert "memory_write_candidates" in write_service_source
    assert "def apply_policy_and_write" in write_service_source
    assert "def apply_policy_and_write_candidate" in write_service_source
    assert "emit_write_event" in session_memory_service_source
    assert "build_session_memory_candidate_identity" in session_memory_service_source
    assert "SESSION_MEMORY_TYPE" not in session_memory_service_source
    assert 'SESSION_MEMORY_TYPE = "session_slot"' in session_memory_repository_source
    assert "class MemoryContextBundle" in context_refs_source
    assert "policy_version" in audit_migration_source
    assert "blocked_by_json" in audit_migration_source
    assert "authority_class" in audit_migration_source
    assert "def list_pending_review" in long_term_repository_source
    assert "def list_pending_review" in case_memory_source
    assert "list_pending_review" in review_api_source


def test_memory_architecture_doc_uses_explicit_preference_long_term_semantics() -> None:
    source = _source(DOC_PATH)

    for expected in (
        "明确只持久化 `memory_kind = preference`",
        "explicit_user_preference",
        "explicit_admin_preference",
        "当前真正接通的长期偏好写入主路径只有管理员 API",
        "async finalizer 与同步 background writer 当前都没有向 `memory_write` 传入 `trusted_context`",
    ):
        assert expected in source


def test_memory_graph_legacy_names_are_historical_projection_only() -> None:
    historical_projections = {
        "session_memory_load": "session_context_load",
        "long_term_memory_retrieve": "memory_context_load",
        "reviewed_memory_context_retrieve": "memory_context_load",
    }

    for legacy_name, target_name in historical_projections.items():
        assert graph_vocabulary_entry(legacy_name, kind="node") is None
        assert target_graph_name(legacy_name, kind="node") == legacy_name
        projected = project_trace_step_for_contract({"node": legacy_name})

        assert projected["implementation_node"] == legacy_name
        assert projected["target_node"] == target_name
        assert projected["target_graph_status"] == "historical_projection"
        assert projected["target_graph_runnable"] is False

    for name in ("session_context_load", "memory_context_load"):
        entry = graph_vocabulary_entry(name, kind="node")
        assert entry is not None
        assert entry.target_name == name
        assert entry.status == "runtime"
        assert entry.runnable is True


def test_memory_contract_boundary_tests_are_present() -> None:
    memory_authority_tests = _source(MEMORY_AUTHORITY_TEST_PATH)
    required_slots_tests = _source(REQUIRED_SLOTS_TEST_PATH)
    long_term_tests = _source(LONG_TERM_TEST_PATH)
    case_memory_tests = _source(CASE_MEMORY_TEST_PATH)
    tombstone_tests = _source(TOMBSTONE_TEST_PATH)
    memory_policy_tests = _source(MEMORY_POLICY_TEST_PATH)
    session_memory_service_tests = _source(SESSION_MEMORY_SERVICE_TEST_PATH)
    memory_write_service_tests = _source(MEMORY_WRITE_SERVICE_TEST_PATH)
    memory_context_bundle_tests = _source(MEMORY_CONTEXT_BUNDLE_TEST_PATH)

    assert "test_session_memory_modules_do_not_import_evidence_ref_v1" in memory_authority_tests
    assert "test_reviewed_memory_cannot_satisfy_policy_evidence_or_action_authority" in memory_authority_tests
    assert (
        "test_contextual_only_memory_refs_do_not_become_evidence_ref_v1_or_business_authority" in memory_authority_tests
    )
    assert (
        "test_trusted_session_memory_rejects_wrong_tenant_user_thread_expired_and_incompatible" in required_slots_tests
    )
    assert "test_current_business_object_long_term_candidate_is_skipped" in long_term_tests
    assert "test_llm_candidate_is_skipped" in long_term_tests
    assert "test_case_memory_tombstone_blocks_writes_by_content_hash_and_source_identity" in case_memory_tests
    assert "test_delayed_rewrite_separate_session_blocks_by_source_identity" in tombstone_tests
    assert "test_case_memory_only_explicit_review_sources_auto_publish" in memory_policy_tests
    assert "test_memory_policy_decision_is_auditable_for_long_term_sources" in memory_policy_tests
    assert "test_memory_write_service_proposes_session_candidate" in memory_write_service_tests
    assert "test_memory_write_service_routes_long_term_candidate_through_facade" in memory_write_service_tests
    assert "test_memory_write_service_routes_case_candidate_through_facade" in memory_write_service_tests
    assert "test_memory_write_service_proposes_explicit_long_term_and_case_candidates_from_state" in (
        memory_write_service_tests
    )
    assert "test_session_memory_write_emits_session_slot_write_event_without_database" in session_memory_service_tests
    assert "test_memory_context_service_projects_agent_facing_bundle_without_merging_authority" in (
        memory_context_bundle_tests
    )

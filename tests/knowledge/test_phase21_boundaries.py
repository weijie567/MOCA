from __future__ import annotations

from pathlib import Path

from src.approvals.snapshots import build_action_safety_snapshot, snapshot_hash_projection
from src.knowledge.config import RERANK_CONFIG_VERSION
from src.knowledge.retrieval import rerank_candidates
from src.knowledge.schemas import EvidenceRefV1, KnowledgeSearchResult, canonical_evidence_projection
from src.replay.schemas import ReplayEventV3


REPO_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IMPLEMENTATION_PATTERNS = {
    "MaterialClaim": "MaterialClaim",
    "semantic_verifier": "semantic_verifier",
    "SemanticVerifier": "SemanticVerifier",
    "QueryRewriteService": "QueryRewriteService",
    "query_rewriter": "query_rewriter",
    "rewrite_query(": "rewrite_query(",
    "CrossEncoderReranker": "CrossEncoderReranker",
    "ExternalRerankClient": "ExternalRerankClient",
    "SearchBackend": "SearchBackend",
    "Vespa": "Vespa",
    "OpenSearch": "OpenSearch",
    "cross_encoder": "cross_encoder",
    "cross-encoder": "cross-encoder",
    "external_action_execution": "external_action_execution",
    "business_data_ingestion_into_rag": "business_data_ingestion_into_rag",
}
IGNORED_STATIC_GUARD_FILES = {
    Path("tests/knowledge/test_phase21_boundaries.py"),
    Path("tests/test_rag_production_migration.py"),
}
ALLOWED_COMPATIBILITY_REFERENCES = {
    Path("src/knowledge/schemas.py"): {
        "query_rewrite",
        "rerank_config_version",
    },
    Path("src/knowledge/config.py"): {
        "RERANK_CONFIG_VERSION",
    },
    Path("src/knowledge/retrieval.py"): {
        "rerank_candidates",
    },
}
PROVENANCE_AUTHORITY_FIELD_NAMES = {
    "DocumentBlock",
    "document_block_id",
    "source_block_id",
    "parser_metadata_json",
    "ocr_metadata_json",
    "rag_ingestion_job_id",
    "ingestion_job_id",
}


def _implementation_python_files() -> list[Path]:
    files: list[Path] = []
    for root in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        files.extend(path for path in root.rglob("*.py") if path.is_file())
    return sorted(
        path
        for path in files
        if path.relative_to(REPO_ROOT) not in IGNORED_STATIC_GUARD_FILES
    )


def test_phase21_does_not_introduce_strict_phase22_23_or_rag5_surfaces() -> None:
    violations: list[str] = []

    for path in _implementation_python_files():
        relative = path.relative_to(REPO_ROOT)
        source = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_IMPLEMENTATION_PATTERNS.items():
            if pattern in source:
                violations.append(f"{relative}: {label}")

    assert violations == []


def test_static_guard_allows_current_v13_compatibility_names_only_at_known_sites() -> None:
    for relative, patterns in ALLOWED_COMPATIBILITY_REFERENCES.items():
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        for pattern in patterns:
            assert pattern in source


def test_deferred_target_state_docs_and_planning_strings_are_outside_static_guard() -> None:
    documentation_candidates = [
        REPO_ROOT / "docs/rag-architecture-spec.md",
        REPO_ROOT / ".planning/phases/21-rag-production-ingestion-ocr/21-RESEARCH.md",
        REPO_ROOT / ".planning/phases/21-rag-production-ingestion-ocr/21-PATTERNS.md",
    ]

    assert any("MaterialClaim" in path.read_text(encoding="utf-8") for path in documentation_candidates)


def test_current_v13_query_rewrite_and_rerank_compatibility_names_remain_allowed() -> None:
    fields = set(KnowledgeSearchResult.model_fields)

    assert "query_rewrite" in fields
    assert RERANK_CONFIG_VERSION == "rerank.v2"
    assert callable(rerank_candidates)


def test_evidence_ref_v1_remains_the_only_policy_evidence_authority_shape() -> None:
    fields = set(EvidenceRefV1.model_fields)

    assert "evidence_id" in fields
    assert "text_hash" in fields
    assert fields == {
        "schema_version",
        "tenant_id",
        "evidence_id",
        "doc_key",
        "chunk_id",
        "policy_version",
        "text_hash",
        "retrieved_at",
        "retrieval_config_version",
        "score",
        "rank",
    }
    assert fields.isdisjoint(PROVENANCE_AUTHORITY_FIELD_NAMES)


def _evidence_ref() -> EvidenceRefV1:
    return EvidenceRefV1(
        tenant_id="tenant-001",
        evidence_id="refund-policy/chunk-001@v3",
        doc_key="refund-policy",
        chunk_id="chunk-001",
        policy_version="v3",
        text_hash="sha256:" + "1" * 64,
        retrieved_at="2026-06-15T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.91,
        rank=1,
    )


def test_canonical_evidence_projection_excludes_source_block_parser_ocr_and_job_fields() -> None:
    projected = canonical_evidence_projection([_evidence_ref()])

    assert len(projected) == 1
    assert set(projected[0]).isdisjoint(PROVENANCE_AUTHORITY_FIELD_NAMES)
    assert "score" not in projected[0]


def test_approval_snapshot_hash_projection_keeps_canonical_evidence_shape() -> None:
    snapshot = build_action_safety_snapshot(
        tenant_id="tenant-001",
        run_id="run-001",
        snapshot_id="snap-001",
        snapshot_ref="snapshot:snap-001",
        policy_config_version="approval-policy.v1",
        risk_config_version="risk-rules.v1",
        retrieval_config_version="retrieval.v3",
        evidence=[_evidence_ref()],
        action_payload_hash="sha256:" + "a" * 64,
        created_at="2026-06-15T00:00:00.000Z",
    )

    projected = snapshot_hash_projection(snapshot)

    assert set(projected["evidence"][0]).isdisjoint(PROVENANCE_AUTHORITY_FIELD_NAMES)
    assert "score" not in projected["evidence"][0]


def test_replay_memory_and_business_tool_contracts_do_not_expose_provenance_authority() -> None:
    replay_fields = set(ReplayEventV3.model_fields)
    assert replay_fields.isdisjoint(PROVENANCE_AUTHORITY_FIELD_NAMES)

    for root in ("src/memory", "src/business", "src/tools"):
        for path in (REPO_ROOT / root).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for forbidden in PROVENANCE_AUTHORITY_FIELD_NAMES:
                assert forbidden not in source, f"{path.relative_to(REPO_ROOT)} exposes {forbidden}"


def test_document_block_ids_are_not_evidence_memory_action_replay_or_business_authority() -> None:
    from src.db.models import DocumentBlock

    fields = set(DocumentBlock.__table__.c.keys())

    assert "source_block_id" in fields
    assert "evidence_id" not in fields
    assert "approval_id" not in fields
    assert "memory_id" not in fields
    assert "action_draft_id" not in fields
    assert "replay_event_id" not in fields
    assert "business_fact_ref" not in fields

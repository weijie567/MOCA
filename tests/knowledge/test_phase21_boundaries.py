from __future__ import annotations

from pathlib import Path

from src.knowledge.config import RERANK_CONFIG_VERSION
from src.knowledge.retrieval import rerank_candidates
from src.knowledge.schemas import EvidenceRefV1, KnowledgeSearchResult
from tests.rag.phase21_xfail_inventory import xfail_for


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
}
IGNORED_STATIC_GUARD_FILES = {
    Path("tests/knowledge/test_phase21_boundaries.py"),
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
    assert "source_block_id" not in fields
    assert "document_block_id" not in fields
    assert "ocr_confidence" not in fields
    assert "parser_metadata_json" not in fields


@xfail_for("21-04a-01/provenance-authority-boundary")
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


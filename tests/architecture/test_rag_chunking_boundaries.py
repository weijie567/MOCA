from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAG_ROOT = ROOT / "src" / "rag"
REPOSITORIES_ROOT = ROOT / "src" / "repositories"
SCRIPTS_ROOT = ROOT / "scripts"


class _CallCollector(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.scopes: list[str] = []
        self.calls: list[tuple[str, str, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scopes.append(node.name)
        self.generic_visit(node)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scopes.append(node.name)
        self.generic_visit(node)
        self.scopes.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name:
            self.calls.append((self.path.relative_to(ROOT).as_posix(), ".".join(self.scopes), name))
        self.generic_visit(node)


class _CurrentSqlCollector(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.scopes: list[str] = []
        self.scope_sources: list[str] = []
        self.operations: list[tuple[str, str, str, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scopes.append(node.name)
        self.scope_sources.append(ast.unparse(node))
        self.generic_visit(node)
        self.scope_sources.pop()
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scopes.append(node.name)
        self.scope_sources.append(ast.unparse(node))
        self.generic_visit(node)
        self.scope_sources.pop()
        self.scopes.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func).rsplit(".", 1)[-1]
        if name in {"select", "select_from", "delete", "update"}:
            models = {
                item.id
                for item in ast.walk(node)
                if isinstance(item, ast.Name) and item.id in {"PolicyChunk", "DocumentBlock"}
            }
            for model in models:
                self.operations.append(
                    (
                        self.path.relative_to(ROOT).as_posix(),
                        ".".join(self.scopes),
                        f"{'select' if name == 'select_from' else name}:{model}",
                        self.scope_sources[-1] if self.scope_sources else "",
                    )
                )
        self.generic_visit(node)


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _production_trees() -> list[tuple[Path, ast.Module]]:
    files = sorted(RAG_ROOT.rglob("*.py")) + sorted(REPOSITORIES_ROOT.rglob("*.py")) + sorted(SCRIPTS_ROOT.glob("*.py"))
    return [(path, ast.parse(path.read_text(encoding="utf-8"))) for path in files]


def test_only_named_compatibility_owner_may_call_legacy_block_chunking() -> None:
    calls: list[tuple[str, str, str]] = []
    for path, tree in _production_trees():
        collector = _CallCollector(path)
        collector.visit(tree)
        calls.extend(collector.calls)

    markdown_callers = [call for call in calls if call[2].rsplit(".", 1)[-1] == "chunk_markdown"]
    block_callers = [call for call in calls if call[2].rsplit(".", 1)[-1] == "chunk_blocks"]
    compatibility_constructors = {
        (path, scope) for path, scope, name in calls if name.rsplit(".", 1)[-1] == "CharacterCompatibilityAssembler"
    }

    assert markdown_callers == []
    assert block_callers == [("src/rag/ingestion.py", "CharacterCompatibilityAssembler.assemble", "chunk_blocks")]
    assert compatibility_constructors == {
        ("src/rag/ingestion.py", "IngestionService.ingest_document"),
        ("src/rag/ingestion.py", "_assembler_for_mode"),
        ("src/rag/ingestion.py", "assembler_for_active_policy_corpus"),
        ("scripts/eval_rag_format_parity.py", "_character_baseline"),
        ("scripts/eval_rag_token_chunk_ab.py", "_character_incumbent"),
        ("scripts/seed_demo.py", "seed_policy_documents"),
    }


def test_no_second_token_or_character_split_loop_exists_outside_approved_owners() -> None:
    approved = {
        "src/rag/chunker.py",
        "src/rag/policy_embedding_input.py",
    }
    budget_names = {
        "max_chars",
        "target_chars",
        "overlap_chars",
        "max_embedding_tokens",
        "target_embedding_tokens",
        "overlap_tokens",
    }
    offenders: list[tuple[str, int, list[str]]] = []
    for path, tree in _production_trees():
        relative = path.relative_to(ROOT).as_posix()
        if relative in approved:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.For | ast.While):
                continue
            names = {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}
            matched = sorted(names & budget_names)
            if matched:
                offenders.append((relative, node.lineno, matched))
    assert offenders == []


def test_embedding_envelopes_are_rendered_only_inside_the_two_named_assemblers() -> None:
    owners: set[tuple[str, str]] = set()
    for path, tree in _production_trees():
        relative = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            has_title = any(isinstance(item, ast.Name) and item.id == "title" for item in ast.walk(node))
            has_source_envelope = any(
                isinstance(item, ast.Constant) and isinstance(item.value, str) and "source_block_id=" in item.value
                for item in ast.walk(node)
            )
            if has_title and has_source_envelope:
                owners.add((relative, node.name))

    assert owners == {
        ("src/rag/ingestion.py", "_render_character_compatibility_input"),
        ("src/rag/policy_embedding_input.py", "_render_embedding_input"),
    }


def test_authoritative_paths_submit_or_validate_exact_assembler_dto_strings() -> None:
    ingestion = (ROOT / "src/rag/ingestion.py").read_text(encoding="utf-8")
    dry_run = (ROOT / "scripts/ingest_policies.py").read_text(encoding="utf-8")
    golden = (ROOT / "scripts/validate_golden_seeds.py").read_text(encoding="utf-8")
    parity = (ROOT / "scripts/check_embedding_tokenizer_parity.py").read_text(encoding="utf-8")
    format_parity = (ROOT / "scripts/eval_rag_format_parity.py").read_text(encoding="utf-8")
    retrieval_rounds = (ROOT / "src/rag/evaluation/retrieval_rounds.py").read_text(encoding="utf-8")

    assert "texts = [dto.embedding_input for dto in assembled_inputs]" in ingestion
    assert "_embedding_text" not in ingestion
    assert "assemble_policy_embedding_inputs(" in dry_run
    assert "assemble_policy_embedding_inputs(" in golden
    assert "embedding_input=final_input.embedding_input" in parity
    assert "input_assembler=_token_candidate()" in format_parity
    assert "input_assembler: PolicyInputAssembler | None = None" in retrieval_rounds
    assert "input_assembler=input_assembler or PolicyEmbeddingInputAssembler()" in retrieval_rounds


def test_every_current_policy_chunk_or_document_block_constructor_has_one_named_owner() -> None:
    calls: set[tuple[str, str, str]] = set()
    for path, tree in _production_trees():
        collector = _CallCollector(path)
        collector.visit(tree)
        calls.update(call for call in collector.calls if call[2].rsplit(".", 1)[-1] in {"PolicyChunk", "DocumentBlock"})

    assert calls == {
        ("src/rag/ingestion.py", "_document_blocks_from_parsed", "DocumentBlock"),
        ("src/rag/ingestion.py", "_policy_chunks_from_embedding_inputs", "PolicyChunk"),
    }


def test_every_current_policy_chunk_or_document_block_sql_path_is_active_scoped() -> None:
    operations: list[tuple[str, str, str, str]] = []
    for path, tree in _production_trees():
        collector = _CurrentSqlCollector(path)
        collector.visit(tree)
        operations.extend(collector.operations)

    actual = {(path, scope, operation) for path, scope, operation, _ in operations}
    assert actual == {
        ("src/rag/search_text_backfill.py", "rebuild_policy_chunk_search_texts", "select:PolicyChunk"),
        (
            "src/repositories/document_block_repo.py",
            "DocumentBlockRepository.delete_by_document_id",
            "delete:DocumentBlock",
        ),
        (
            "src/repositories/document_block_repo.py",
            "DocumentBlockRepository.get_by_source_block_ids",
            "select:DocumentBlock",
        ),
        (
            "src/repositories/document_block_repo.py",
            "DocumentBlockRepository.list_by_document_id",
            "select:DocumentBlock",
        ),
        (
            "src/repositories/document_block_repo.py",
            "DocumentBlockRepository.load_authoritative_snapshot",
            "select:DocumentBlock",
        ),
        (
            "src/repositories/evidence_version_repo.py",
            "EvidenceVersionRepository._active_chunks_for_update",
            "select:PolicyChunk",
        ),
        (
            "src/repositories/evidence_version_repo.py",
            "EvidenceVersionRepository.get_current_identities_by_keys",
            "select:PolicyChunk",
        ),
        ("src/rag/ingestion.py", "IngestionService.ingest_document", "delete:DocumentBlock"),
        ("src/rag/policy_reindex.py", "PolicyReindexService.validate_candidate", "select:PolicyChunk"),
        (
            "src/repositories/policy_chunk_repo.py",
            "PolicyChunkRepository.delete_by_document_id",
            "delete:PolicyChunk",
        ),
        *{
            ("src/repositories/policy_chunk_repo.py", f"PolicyChunkRepository.{method}", "select:PolicyChunk")
            for method in {
                "get_canonical_evidence_rows_by_keys",
                "get_contents_by_evidence_keys",
                "get_provenance_by_evidence_keys",
                "list_by_document_id_for_update",
                "search_fuzzy",
                "search_similar",
                "search_sparse",
            }
        },
        (
            "src/repositories/policy_corpus_scope.py",
            "active_block_ids",
            "select:DocumentBlock",
        ),
        (
            "src/repositories/policy_corpus_scope.py",
            "active_chunk_ids",
            "select:PolicyChunk",
        ),
        *{
            (
                "src/repositories/rag_evaluation_round_repo.py",
                f"RagEvaluationRoundRepository.{method}",
                f"select:{model}",
            )
            for method, model in {
                ("capture_rollback_baseline", "DocumentBlock"),
                ("capture_rollback_baseline", "PolicyChunk"),
                ("_head_projection", "DocumentBlock"),
                ("_head_projection", "PolicyChunk"),
                ("_head_resource_proof", "PolicyChunk"),
                ("_inspect_locked", "DocumentBlock"),
                ("_inspect_locked", "PolicyChunk"),
                ("prove_recorded_anchor_locators", "DocumentBlock"),
                ("prove_recorded_anchor_locators", "PolicyChunk"),
                ("_current_counts", "DocumentBlock"),
                ("_current_counts", "PolicyChunk"),
            }
        },
    }
    scope_tokens = {
        "join_active_chunk_projection",
        "join_active_block_projection",
        "active_chunk_ids",
        "active_block_ids",
        "CorpusChunkBinding",
        "CorpusBlockBinding",
        "_pre_token_corpus_schema",
    }
    assert all(any(token in source for token in scope_tokens) for _, _, _, source in operations)


def test_current_mutation_and_maintenance_paths_require_active_scope() -> None:
    ingestion = (ROOT / "src/rag/ingestion.py").read_text(encoding="utf-8")
    backfill = (ROOT / "src/rag/search_text_backfill.py").read_text(encoding="utf-8")
    seed = (ROOT / "scripts/seed_demo.py").read_text(encoding="utf-8")
    chunk_repo = (ROOT / "src/repositories/policy_chunk_repo.py").read_text(encoding="utf-8")
    block_repo = (ROOT / "src/repositories/document_block_repo.py").read_text(encoding="utf-8")

    assert "await ActivePolicyCorpusScope.resolve(" in ingestion
    assert "assembler_for_active_policy_corpus" in ingestion
    assert "ensure_tenant_character_bootstrap" in ingestion
    assert "create_ingestion_cow" in ingestion
    assert "join_active_chunk_projection" in backfill
    assert "tenant_id: UUID," in backfill
    assert "ActivePolicyCorpusScope.resolve" in seed
    assert "assembler_for_active_policy_corpus" in seed
    assert "await ActivePolicyCorpusScope.resolve(" in chunk_repo
    assert "await ActivePolicyCorpusScope.resolve(" in block_repo


def test_identity_and_compatibility_authorities_are_corpus_free_and_source_based() -> None:
    identity = (ROOT / "src/knowledge/evidence_identity.py").read_text(encoding="utf-8")
    evidence_repo = (ROOT / "src/repositories/evidence_version_repo.py").read_text(encoding="utf-8")
    ingestion = (ROOT / "src/rag/ingestion.py").read_text(encoding="utf-8")

    for function_name in (
        "canonical_document_version_matches_source",
        "canonical_chunk_version_matches_projection",
    ):
        function = next(
            node
            for node in ast.parse(evidence_repo).body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        assert "corpus_version_id" not in ast.unparse(function)
    assert "corpus_version_id" not in identity
    assert "_document_citation_text" not in ingestion
    assert "canonical_source = build_canonical_document_content(blocks)" in ingestion

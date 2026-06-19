---
phase: 21-rag-production-ingestion-ocr
artifact: final-acceptance
status: ACCEPTED
baseline: f84b2bd
created_utc: 2026-06-18T23:56:50Z
post_dependency_gate_utc: 2026-06-19T04:07:57Z
requirements:
  - SRC-01
  - SRC-02
  - SRC-03
  - SRC-04
  - SRC-05
  - PROV-01
  - PROV-02
  - PROV-03
  - PROV-04
  - CHUNK-01
  - CHUNK-02
  - CHUNK-03
  - CHUNK-04
  - OCR-01
  - OCR-02
  - SAFE-01
  - SAFE-02
  - SAFE-03
  - INGEST-01
  - INGEST-02
  - INGEST-03
  - INGEST-04
  - BOUNDARY-01
  - BOUNDARY-02
  - BOUNDARY-03
  - BOUNDARY-04
threat_refs:
  - T21-01
  - T21-02
  - T21-03
  - T21-04
  - T21-05
  - T21-06
  - T21-07
  - T21-08
---

# Phase 21 Final Acceptance

**Acceptance status:** `ACCEPTED`

All 26 Phase 21 requirement IDs and all eight Phase 21 threat refs have automated coverage from passing tests. No implementation gap is being accepted as complete.

Post-dependency gate status:

- Native `chi_sim` traineddata is installed locally. OCR preflight now reports `available=True` with `missing_languages=()`.
- Optional live DB migration round trip was executed against a disposable `pgvector/pgvector:pg16` PostgreSQL database via `MOCA_TEST_DATABASE_URL`.

## Command Evidence

### Focused Phase 21 Suite

Command:

```bash
uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag tests/knowledge -q
```

Result:

```text
........................................................................ [ 37%]
........................................................................ [ 75%]
...............................................                          [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py:5
  /Users/ming/projects/MOCA/.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py:5: LangChainPendingDeprecationWarning: The default value of `allowed_objects` will change in a future version. Pass an explicit value (e.g., allowed_objects='messages' or allowed_objects='core') to suppress this warning.
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
191 passed, 1 warning in 4.49s
```

### Full Pytest Gate

Command:

```bash
MOCA_TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:54329/moca_phase21_migration_test" \
  uv run pytest -q --tb=short -rs
```

Result:

```text
1136 passed, 9 warnings in 543.23s (0:09:03)
```

No skipped tests were reported in the post-dependency full pytest gate.

### Ruff Gate

Command:

```bash
uv run ruff check src tests
```

Result:

```text
All checks passed!
```

### Migration Downgrade/Reupgrade Status

Command:

```bash
MOCA_TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:54329/moca_phase21_migration_test" \
  uv run pytest tests/test_rag_production_migration.py tests/rag/test_ocr_parser.py tests/rag/test_pdf_parser.py -q -rs
```

Result:

```text
............................                                             [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py:5
  /Users/ming/projects/MOCA/.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py:5: LangChainPendingDeprecationWarning: The default value of `allowed_objects` will change in a future version. Pass an explicit value (e.g., allowed_objects='messages' or allowed_objects='core') to suppress this warning.
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

tests/test_rag_production_migration.py::test_phase21_migration_live_downgrade_round_trip_when_configured
tests/test_rag_production_migration.py::test_phase21_migration_live_downgrade_round_trip_when_configured
tests/test_rag_production_migration.py::test_phase21_migration_live_downgrade_round_trip_when_configured
  /Users/ming/projects/MOCA/.venv/lib/python3.12/site-packages/alembic/config.py:612: DeprecationWarning: No path_separator found in configuration; falling back to legacy splitting on spaces, commas, and colons for prepend_sys_path.  Consider adding path_separator=os to Alembic config.
    util.warn_deprecated(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
28 passed, 4 warnings in 1.32s
```

Environment confirmation:

```text
MOCA_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:54329/moca_phase21_migration_test
database_image=pgvector/pgvector:pg16
```

Decision: `INGEST-04` is accepted on static migration coverage plus live disposable PostgreSQL downgrade/reupgrade coverage.

### OCR Runtime Preflight Status

Command:

```bash
uv run python - <<'PY'
from src.rag.parsers.runtime import check_ocr_runtime
result = check_ocr_runtime()
print(f"available={result.available}")
print(f"failure_code={result.failure_code}")
print(f"installed_languages={result.installed_languages}")
print(f"missing_languages={result.missing_languages}")
print(f"version={result.version}")
PY
```

Result:

```text
available=True
failure_code=None
installed_languages includes chi_sim and eng
missing_languages=()
version=tesseract 5.5.2
```

Decision: `SRC-05` and `OCR-02` are accepted with passing parser/OCR tests and live native `chi_sim+eng` OCR preflight.

### Wave 0 / Xfail Inventory Status

Command:

```bash
uv run python - <<'PY'
from pathlib import Path
namespace = {}
exec(Path('tests/rag/phase21_xfail_inventory.py').read_text(encoding='utf-8'), namespace)
owners = namespace['PHASE21_XFAIL_OWNERS']
print(f"PHASE21_XFAIL_OWNERS={owners}")
print(f"implementation_pending_owner_count={len(owners)}")
PY
```

Result:

```text
PHASE21_XFAIL_OWNERS={}
implementation_pending_owner_count=0
```

Command:

```bash
rg -n "target code absent|owner_task=21-|xfail" tests/rag tests/knowledge tests/test_ingestion.py tests/test_rag_production_migration.py
printf 'exit_code=%s\n' "$?"
```

Result:

```text
exit_code=1
```

Interpretation: `rg` exit code 1 means no matches. There are no implementation-pending Phase 21 xfails in the scoped test files.

### Final Scope Guard

Command:

```bash
uv run pytest tests/knowledge/test_phase21_boundaries.py -q
```

Result:

```text
.............                                                            [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py:5
  /Users/ming/projects/MOCA/.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py:5: LangChainPendingDeprecationWarning: The default value of `allowed_objects` will change in a future version. Pass an explicit value (e.g., allowed_objects='messages' or allowed_objects='core') to suppress this warning.
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
13 passed, 1 warning in 0.11s
```

Scope decision:

- Confirmed absent from implementation: Phase 22 `MaterialClaim` / semantic verifier surfaces, Phase 23 query rewrite service / reranker service/interface/API / cross-encoder/external rerank API surfaces, Phase RAG-5 `SearchBackend` / Vespa / OpenSearch surfaces, real external action execution, and business data ingestion into RAG.
- Explicitly allowed current v1.3 compatibility names only at known sites: `KnowledgeSearchResult.query_rewrite`, `RERANK_CONFIG_VERSION`, `rerank_config_version`, `rerank_candidates(...)`, and existing hybrid retrieval tests.
- Documentation/planning target-state mentions are outside the implementation guard and do not count as delivered Phase 22/23/RAG-5 scope.

## Requirement Coverage

| Requirement | Status | Evidence |
|---|---|---|
| SRC-01 | Covered | `tests/rag/test_parser_contract.py`; focused suite passed. |
| SRC-02 | Covered | `tests/rag/test_parser_contract.py`; focused suite passed. |
| SRC-03 | Covered | `tests/rag/test_pdf_parser.py`; focused suite passed. |
| SRC-04 | Covered | `tests/rag/test_docx_parser.py`; focused suite passed. |
| SRC-05 | Covered | `tests/rag/test_ocr_parser.py`; focused suite passed; live native preflight reports `chi_sim+eng` available. |
| PROV-01 | Covered | `tests/rag/test_document_block_schema.py`; focused suite passed. |
| PROV-02 | Covered | `tests/rag/test_block_chunker.py`; focused suite passed. |
| PROV-03 | Covered | `tests/knowledge/test_provenance_lookup.py`; focused suite passed. |
| PROV-04 | Covered | `tests/knowledge/test_phase21_boundaries.py`; scope guard passed. |
| CHUNK-01 | Covered | `tests/rag/test_block_chunker.py`, `tests/test_chunker.py`; focused suite passed. |
| CHUNK-02 | Covered | `tests/rag/test_block_chunker.py`, parser table fixtures; focused suite passed. |
| CHUNK-03 | Covered | `tests/rag/test_block_chunker.py`, `tests/rag/test_search_text.py`, `tests/knowledge/test_text_hash.py`; focused suite passed. |
| CHUNK-04 | Covered | `tests/test_ingestion.py`, versioning tests; focused suite passed. |
| OCR-01 | Covered | `tests/rag/test_ocr_parser.py`, hybrid retrieval boundary tests; focused suite passed. |
| OCR-02 | Covered | OCR confidence threshold and fail-closed preflight tests passed; native `chi_sim+eng` preflight passed locally. |
| SAFE-01 | Covered | `tests/rag/test_ingestion_safety.py`, `tests/rag/test_ocr_parser.py`; focused suite passed. |
| SAFE-02 | Covered | `tests/rag/test_ingestion_safety.py`, `tests/rag/test_ingestion_jobs.py`, `tests/knowledge/test_phase21_boundaries.py`; focused suite passed. |
| SAFE-03 | Covered | `tests/rag/test_ingestion_safety.py`, `tests/test_ingestion.py`; focused suite passed. |
| INGEST-01 | Covered | `tests/rag/test_ingestion_jobs.py`; focused suite passed. |
| INGEST-02 | Covered | `tests/test_ingestion.py`, `tests/rag/test_ingestion_jobs.py`; focused suite passed. |
| INGEST-03 | Covered | `tests/test_ingestion.py`, `tests/rag/test_ingestion_jobs.py`; focused suite passed. |
| INGEST-04 | Covered | `tests/test_rag_production_migration.py` static migration tests passed; live DB downgrade/reupgrade passed against disposable `pgvector/pgvector:pg16`. |
| BOUNDARY-01 | Covered | `tests/knowledge/test_phase21_boundaries.py` plus full suite evidence/snapshot/replay tests; full pytest passed. |
| BOUNDARY-02 | Covered | `tests/knowledge/test_hybrid_retrieval.py`, `tests/knowledge/test_hybrid_schema.py`; focused/full suites passed. |
| BOUNDARY-03 | Covered | `tests/knowledge/test_phase21_boundaries.py`; scope guard passed. |
| BOUNDARY-04 | Covered | `tests/knowledge/test_phase21_boundaries.py`; scope guard passed. |

## Threat Coverage

| Threat | Status | Evidence |
|---|---|---|
| T21-01 | Mitigated | Source type/signature routing and parser/source guard tests passed. |
| T21-02 | Mitigated | Size/page/image/zip hazard tests and static migration rollback tests passed; live DB round trip passed against disposable `pgvector/pgvector:pg16`. |
| T21-03 | Mitigated | Parser/OCR timeout and rollback tests passed; native OCR preflight reports `chi_sim+eng` available. |
| T21-04 | Mitigated | Hidden prompt injection, raw payload, prompt/API/memory/action/replay boundary tests passed. |
| T21-05 | Mitigated | Verified tenant/hash provenance lookup and cross-tenant/hash mismatch tests passed. |
| T21-06 | Mitigated | Business artifact and Tool System output rejection tests passed. |
| T21-07 | Mitigated | `DocumentBlock` authority boundary, evidence shape, approval snapshot, replay, memory, business/tool boundary tests passed. |
| T21-08 | Mitigated | Safe ingestion report and sanitized trace/error projection tests passed. |

## Implementation Gaps

None.

## Residual Risk

- Runtime/CI environments must retain `chi_sim` traineddata and pgvector-capable PostgreSQL for these live gates to remain executable.
- The full suite emits only existing dependency/deprecation warnings; no Phase 21 acceptance blocker remains.

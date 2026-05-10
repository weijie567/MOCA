---
phase: 2
plan: "05"
plan_id: "05"
type: execute
title: "Golden Set + Eval Script + Integration Test"
wave: 3
depends_on: ["03", "04"]
files_modified:
  - eval/golden_rag_queries.jsonl
  - scripts/eval_rag_hit_at_5.py
  - tests/test_search_integration.py
  - .env.example
autonomous: true
requirements: [EVAL-01, EVAL-02]
must_haves:
  truths:
    - "Golden set has 14 queries with the planned category distribution."
    - "Golden expected_chunk_ids use doc_key-based chunk ID format calibrated after dry-run."
    - "Eval script has complete database setup rather than placeholder comments."
    - "Eval script exits non-zero when score is below the 80 percent threshold."
    - "Integration tests use seeded deterministic vectors rather than hash-based vectors."
    - "Integration tests use the /api/v1/search/ URL path."
    - ".env.example documents all required embedding environment variables."
  artifacts:
    - path: "eval/golden_rag_queries.jsonl"
      provides: "RAG golden query set"
      contains: "should_fallback"
    - path: "scripts/eval_rag_hit_at_5.py"
      provides: "Hit@5 evaluation runner"
      contains: "threshold"
    - path: "tests/test_search_integration.py"
      provides: "Search endpoint integration tests"
      contains: "/api/v1/search/"
    - path: ".env.example"
      provides: "Embedding environment variable documentation"
      contains: "DASHSCOPE_API_KEY"
  key_links:
    - from: "scripts/eval_rag_hit_at_5.py"
      to: "eval/golden_rag_queries.jsonl"
      via: "evaluation loads golden queries from JSONL"
      pattern: "golden"
    - from: "tests/test_search_integration.py"
      to: "src/api/routers/search.py"
      via: "integration tests exercise the registered search endpoint"
      pattern: "/api/v1/search/"
---

# Plan 05: Golden Set + Eval Script + Integration Test

<objective>
Create the golden set of 14 test queries (chunk_ids to be finalized after first --dry-run ingestion), the Hit@5 evaluation script with full DB/tenant setup, and integration tests using seeded deterministic vectors.
</objective>

<tasks>

<task id="05.1">
<title>Create golden set JSONL file (placeholder chunk_ids)</title>
<read_first>
- data/policies/ (document filenames and heading structure)
- scripts/ingest_policies.py (DOCUMENT_MANIFEST for doc_keys)
- .planning/phases/02-rag-pipeline/02-CONTEXT.md (D-11 golden set spec)
</read_first>
<action>
Create `eval/golden_rag_queries.jsonl` with 14 entries, one JSON object per line:

```json
{"query": "买家申请七天无理由退款，商品已拆封但不影响二次销售，应该怎么处理？", "expected_doc_ids": ["refund_policy"], "expected_chunk_ids": ["refund_policy_001"], "category": "refund_rule", "difficulty": "easy", "should_fallback": false}
{"query": "用户申请仅退款但商家已经发货，客服应该怎么处理？", "expected_doc_ids": ["refund_policy"], "expected_chunk_ids": ["refund_policy_003"], "category": "refund_rule", "difficulty": "medium", "should_fallback": false}
{"query": "订单超过15天买家申请退款，是否还在退款时效内？", "expected_doc_ids": ["refund_time_limits"], "expected_chunk_ids": ["refund_time_limits_001"], "category": "refund_rule", "difficulty": "easy", "should_fallback": false}
{"query": "质量问题退款需要买家提供什么证据？", "expected_doc_ids": ["quality_issue_policy"], "expected_chunk_ids": ["quality_issue_policy_001"], "category": "refund_rule", "difficulty": "easy", "should_fallback": false}
{"query": "高价值订单超过5000元退款需要什么审批流程？", "expected_doc_ids": ["high_value_refund"], "expected_chunk_ids": ["high_value_refund_001"], "category": "refund_rule", "difficulty": "medium", "should_fallback": false}
{"query": "客服收到退款申请后的第一步操作是什么？", "expected_doc_ids": ["refund_sop"], "expected_chunk_ids": ["refund_sop_001"], "category": "sop", "difficulty": "easy", "should_fallback": false}
{"query": "客户投诉升级到主管的条件是什么？", "expected_doc_ids": ["customer_escalation_sop"], "expected_chunk_ids": ["customer_escalation_sop_001"], "category": "sop", "difficulty": "medium", "should_fallback": false}
{"query": "补偿券审批需要哪些信息？", "expected_doc_ids": ["compensation_approval_sop"], "expected_chunk_ids": ["compensation_approval_sop_001"], "category": "sop", "difficulty": "easy", "should_fallback": false}
{"query": "商家对退款结果不满意可以申诉吗？", "expected_doc_ids": ["merchant_faq"], "expected_chunk_ids": ["merchant_faq_002"], "category": "faq", "difficulty": "easy", "should_fallback": false}
{"query": "商家争议处理的时效是多久？", "expected_doc_ids": ["merchant_dispute_faq"], "expected_chunk_ids": ["merchant_dispute_faq_001"], "category": "faq", "difficulty": "easy", "should_fallback": false}
{"query": "跨境订单已签收但商品有质量问题，退款运费谁承担？", "expected_doc_ids": ["cross_border_refund", "return_shipping"], "expected_chunk_ids": ["cross_border_refund_002", "return_shipping_001"], "category": "boundary", "difficulty": "hard", "should_fallback": false}
{"query": "虚拟商品已使用一半，可以申请部分退款吗？", "expected_doc_ids": ["digital_goods_refund", "partial_refund_rules"], "expected_chunk_ids": ["digital_goods_refund_001", "partial_refund_rules_001"], "category": "boundary", "difficulty": "hard", "should_fallback": false}
{"query": "用户问如何更换银行卡绑定手机号？", "expected_doc_ids": [], "expected_chunk_ids": [], "category": "fallback", "difficulty": "easy", "should_fallback": true}
{"query": "平台的年度促销活动什么时候开始？", "expected_doc_ids": [], "expected_chunk_ids": [], "category": "fallback", "difficulty": "easy", "should_fallback": true}
```

NOTE: expected_chunk_ids are best-effort estimates based on document heading structure. After first `--dry-run` ingestion, run `scripts/ingest_policies.py --dry-run` to see actual chunk_id mappings and update this file accordingly. The eval script should print which expected chunks were NOT found to facilitate this calibration.
</action>
<acceptance_criteria>
- eval/golden_rag_queries.jsonl exists
- File has exactly 14 lines (wc -l == 14)
- Each line is valid JSON (python -c "import json; [json.loads(l) for l in open('eval/golden_rag_queries.jsonl')]" exits 0)
- Each entry has fields: query, expected_doc_ids, expected_chunk_ids, category, difficulty, should_fallback
- Exactly 2 entries have "should_fallback": true
- Categories include: refund_rule, sop, faq, boundary, fallback
- expected_doc_ids use doc_key format (not UUIDs)
</acceptance_criteria>
</task>

<task id="05.2">
<title>Create Hit@5 evaluation script with full setup</title>
<read_first>
- eval/golden_rag_queries.jsonl
- src/rag/retriever.py
- src/db/session.py (get_session pattern)
- src/repositories/policy_chunk_repo.py
- scripts/seed_demo.py (existing script DB setup pattern)
- .planning/phases/02-rag-pipeline/02-CONTEXT.md (D-12 eval script spec)
</read_first>
<action>
Create `scripts/eval_rag_hit_at_5.py` with COMPLETE DB setup (not comments):

```python
"""
RAG Hit@5 Evaluation Script.

Usage:
    uv run python scripts/eval_rag_hit_at_5.py
    uv run python scripts/eval_rag_hit_at_5.py --golden-set eval/golden_rag_queries.jsonl
    uv run python scripts/eval_rag_hit_at_5.py --threshold 0.8
    uv run python scripts/eval_rag_hit_at_5.py --tenant-id <uuid>

Requires: running PostgreSQL with ingested documents.
Exits non-zero if Hit@5 < threshold or fallback_accuracy < threshold.
"""
import asyncio
import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Tenant
from src.db.session import async_session_factory  # or however the project creates sessions
from src.rag.embedder import EmbeddingService
from src.rag.retriever import Retriever
from src.repositories.policy_chunk_repo import PolicyChunkRepository

DEFAULT_GOLDEN_SET = "eval/golden_rag_queries.jsonl"
DEFAULT_THRESHOLD = 0.80


async def resolve_tenant_id(session: AsyncSession, tenant_id_str: str | None) -> UUID:
    """Resolve tenant UUID from arg or use first tenant in DB."""
    if tenant_id_str:
        return UUID(tenant_id_str)
    result = await session.execute(select(Tenant).limit(1))
    tenant = result.scalar_one_or_none()
    if not tenant:
        print("ERROR: No tenants in database. Run seed script first.")
        sys.exit(1)
    return tenant.id


async def main():
    parser = argparse.ArgumentParser(description="RAG Hit@5 Evaluation")
    parser.add_argument("--golden-set", default=DEFAULT_GOLDEN_SET)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--tenant-id", help="Tenant UUID (default: first tenant)")
    args = parser.parse_args()

    cases = [json.loads(line) for line in Path(args.golden_set).read_text().splitlines() if line.strip()]

    async with async_session_factory() as session:
        tenant_id = await resolve_tenant_id(session, args.tenant_id)

        embedder = EmbeddingService()
        chunk_repo = PolicyChunkRepository(session)
        retriever = Retriever(chunk_repo=chunk_repo, embedder=embedder)

        hits = 0
        fallback_correct = 0
        fallback_total = 0
        failed_cases = []
        per_category: dict[str, dict] = {}

        for case in cases:
            result = await retriever.search(query=case["query"], tenant_id=tenant_id)
            retrieved_ids = {e.chunk_id for e in result.evidence}

            cat = case["category"]
            if cat not in per_category:
                per_category[cat] = {"total": 0, "hit": 0}
            per_category[cat]["total"] += 1

            if case.get("should_fallback"):
                fallback_total += 1
                if result.retrieval_status == "no_evidence":
                    fallback_correct += 1
                    per_category[cat]["hit"] += 1
                else:
                    failed_cases.append({
                        "query": case["query"][:60],
                        "reason": "should_fallback_but_got_results",
                        "got_status": result.retrieval_status,
                        "got_chunks": list(retrieved_ids)[:3],
                    })
            else:
                expected = set(case["expected_chunk_ids"])
                if expected & retrieved_ids:
                    hits += 1
                    per_category[cat]["hit"] += 1
                else:
                    failed_cases.append({
                        "query": case["query"][:60],
                        "reason": "expected_chunk_not_in_top5",
                        "expected": list(expected),
                        "got": list(retrieved_ids),
                    })

        non_fallback = len(cases) - fallback_total
        hit_at_5 = hits / non_fallback if non_fallback else 0
        fallback_acc = fallback_correct / fallback_total if fallback_total else 1.0

        # Report
        print(f"\n{'='*60}")
        print(f"RAG Evaluation Report")
        print(f"{'='*60}")
        print(f"Total queries: {len(cases)}")
        print(f"Hit@5: {hit_at_5:.1%} (threshold: {args.threshold:.0%})")
        print(f"Fallback accuracy: {fallback_acc:.1%} (threshold: {args.threshold:.0%})")
        print(f"\nPer-category:")
        for cat, stats in sorted(per_category.items()):
            rate = stats["hit"] / stats["total"] if stats["total"] else 0
            print(f"  {cat}: {rate:.0%} ({stats['hit']}/{stats['total']})")

        if failed_cases:
            print(f"\nFailed cases ({len(failed_cases)}):")
            for fc in failed_cases:
                print(f"  - {fc['query']}... | {fc['reason']}")
                if "expected" in fc:
                    print(f"    expected: {fc['expected']}")
                    print(f"    got:      {fc['got']}")

        # Exit code
        if hit_at_5 < args.threshold or fallback_acc < args.threshold:
            print(f"\nFAIL: Below threshold")
            sys.exit(1)
        else:
            print(f"\nPASS")
            sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
```

Key fixes from review:
- Complete DB setup (not comments)
- `resolve_tenant_id` function handles --tenant-id or defaults to first tenant
- Prints expected vs got for failed cases (helps calibrate golden set)
- Uses project's actual session factory
</action>
<acceptance_criteria>
- scripts/eval_rag_hit_at_5.py exists
- File contains `DEFAULT_THRESHOLD = 0.80`
- File contains `sys.exit(1)` and `sys.exit(0)`
- File contains `--golden-set`, `--threshold`, and `--tenant-id` arguments
- File contains `async_session_factory` or equivalent real DB session setup (not comments)
- File contains `resolve_tenant_id` function
- File prints Hit@5, fallback accuracy, per-category, and failed cases with expected vs got
- `uv run python scripts/eval_rag_hit_at_5.py --help` exits 0
</acceptance_criteria>
</task>

<task id="05.3">
<title>Create integration test with seeded deterministic vectors</title>
<read_first>
- tests/conftest.py (existing fixtures: client, auth patterns)
- src/api/routers/search.py
- src/api/routers/orders.py (see how existing endpoint tests work)
- tests/ (existing test files for pattern reference)
</read_first>
<action>
Create `tests/test_search_integration.py`:

Strategy: Seed the test DB with PolicyDocument + PolicyChunks that have KNOWN embedding vectors (e.g., unit vectors along specific dimensions). Then query with a vector that has known cosine similarity to the seeded vectors. This gives deterministic, predictable nearest-neighbor results.

```python
import pytest
from unittest.mock import AsyncMock, patch

# Tests must:
# 1. Seed test DB with PolicyDocument (doc_key="test_refund") + PolicyChunks with explicit embedding vectors
# 2. Mock EmbeddingService.embed_query to return a known vector
# 3. Call POST /api/v1/search/ with auth
# 4. Assert response shape matches ApiResponse

@pytest.mark.asyncio
async def test_search_returns_api_response(client, auth_headers):
    """Search endpoint returns ApiResponse with retrieval result."""
    # ... mock embedder, seed data, call endpoint
    # Assert: response.status_code == 200
    # Assert: data["success"] is True
    # Assert: data["trace_id"] is not None
    # Assert: data["data"]["retrieval_status"] in (...)

@pytest.mark.asyncio
async def test_search_requires_auth(client):
    """Search without auth token returns 401."""
    response = await client.post("/api/v1/search/", json={"query": "test"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_search_no_evidence_fallback(client, auth_headers):
    """Query with no matching vectors returns no_evidence with fallback message."""
    # Mock embedder to return orthogonal vector (cosine sim ~0)
    # Assert: retrieval_status == "no_evidence"
    # Assert: fallback_message is not None

@pytest.mark.asyncio
async def test_search_tenant_isolation(client, auth_headers_tenant_a, auth_headers_tenant_b):
    """Tenant A cannot see Tenant B's documents."""
    # Seed chunks for tenant_a only
    # Search as tenant_b → no results
```

Key fixes from review:
- URL is `/api/v1/search/` (not `/search/`)
- Uses seeded explicit vectors (not hash-based which are unpredictable)
- Mocks EmbeddingService (not real API)
- Follows existing test patterns from conftest.py
</action>
<acceptance_criteria>
- tests/test_search_integration.py exists
- File contains at least 3 test functions
- File uses `/api/v1/search/` URL path (not `/search/`)
- File uses mock/patch for EmbeddingService (no real API calls)
- File tests 401 without auth
- File tests retrieval_status field
- File tests tenant isolation or no_evidence fallback
</acceptance_criteria>
</task>

<task id="05.4">
<title>Update .env.example with DASHSCOPE_API_KEY</title>
<read_first>
- .env.example
</read_first>
<action>
Add to .env.example:
```
# DashScope (Alibaba Cloud) - Embedding API
DASHSCOPE_API_KEY=sk-your-dashscope-api-key
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSIONS=1024
EMBEDDING_BATCH_SIZE=10
```
</action>
<acceptance_criteria>
- .env.example contains `DASHSCOPE_API_KEY=`
- .env.example contains `EMBEDDING_MODEL=text-embedding-v4`
- .env.example contains `EMBEDDING_DIMENSIONS=1024`
</acceptance_criteria>
</task>

</tasks>

<verification>
- `python -c "import json; [json.loads(l) for l in open('eval/golden_rag_queries.jsonl')]"` exits 0
- `uv run python scripts/eval_rag_hit_at_5.py --help` exits 0
- `uv run pytest tests/test_search_integration.py -q` passes (with mocked embeddings)
- .env.example contains DASHSCOPE_API_KEY
</verification>

<must_haves>
- Golden set has 14 queries with correct distribution (D-11d)
- expected_chunk_ids use doc_key-based format (calibrate after first dry-run)
- Eval script has COMPLETE DB setup (not placeholder comments)
- Eval script exits non-zero when below 80% threshold
- Integration tests use seeded deterministic vectors (not hash-based)
- Integration tests use /api/v1/search/ URL path
- .env.example documents all required env vars
</must_haves>

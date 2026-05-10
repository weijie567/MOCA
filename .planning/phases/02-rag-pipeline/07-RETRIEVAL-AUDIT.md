# Phase 2 Plan 07 Retrieval Audit

## Baseline

Plan 06 is the source of truth for the pre-fix retrieval gap.

- Hit@5: 58.3%
- Fallback accuracy: 100.0%
- Non-fallback hits: 7/12
- Required non-fallback hits for the 80% gate: 10/12

Plan 06 proved golden-set calibration alone cannot honestly close EVAL-02. Only one failed case had an answer-bearing candidate that could be safely added to labels, which would raise live retrieval from 7/12 to 8/12, still below the gate.

## Before Plan 07

| Failed query category | Evidence from Plan 06 | Reason |
| --- | --- | --- |
| `refund_rule` 七天无理由拆封 | No sufficient answer-bearing expected-doc chunk in top-5 | `refund_policy_002` discusses exceptions but does not directly answer the positive handling rule for goods that do not affect secondary sale. |
| `refund_rule` 超过15天 | No answer-bearing expected chunk in top-5 | Only `refund_time_limits_000` intro appeared from the expected document and it is not answer-bearing. |
| `sop` 补偿券审批信息 | Expected answer `compensation_approval_sop_002` absent from top-5 | Retrieved expected-doc chunks covered approval levels or post-approval writeback, not submitted materials. |
| `faq` 商家争议时效 | No `merchant_dispute_faq` chunk in top-5 | The expected document was absent from final evidence. |
| `boundary` 跨境质量问题运费 | `cross_border_refund_002` appeared at rank 1, score 0.7611 | Semantically valid calibration candidate, but accepting it would still leave Hit@5 below 80%. |

The official eval remains exact `expected_chunk_ids` Hit@5 plus fallback accuracy. Diagnostic evidence depth may be increased for audit output, but pass/fail scoring stays at `top_k=5` with `DEFAULT_THRESHOLD = 0.80`.

## After Plan 07

Live re-ingestion command:

`set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7`

Result: 15/15 documents succeeded, 90 chunks regenerated with enriched embedding input.

Live eval command:

`set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7`

Result: PASS.

- Hit@5: 83.3%
- Fallback accuracy: 100.0%
- Non-fallback hits: 10/12
- Fallback hits: 2/2

The first post-rerank live eval reached Hit@5 83.3% but regressed fallback accuracy to 0.0% because the query prefix pulled weak policy matches for out-of-domain questions. Plan 07 fixed that regression with a deterministic support-domain anchor guard while preserving `MIN_SIMILARITY_THRESHOLD = 0.55`; support-domain queries still retrieve through `PolicyChunkRepository.search_similar()`, and out-of-domain queries fall back instead of surfacing weak policy evidence.

## After Plan 07 Failed-Case Diagnostics

Diagnostic command:

`set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7 --diagnostic-top-k 20`

Result: PASS with two remaining non-fallback misses that do not block EVAL-02.

| Query | Final top-5 result | Diagnostic top-20 evidence |
| --- | --- | --- |
| `质量问题退款需要买家提供什么证据？` | Missed exact labels `quality_issue_policy_001` and `refund_policy_004`; top-5 contains answer-bearing quality evidence including `refund_policy_003`, `merchant_faq_003`, `quality_issue_policy_004`, and `quality_issue_policy_005`. | Expected chunks appear at diagnostic ranks 6 and 7, so bounded reranking improved recall but did not force all semantically related expected labels into top-5. |
| `商家争议处理的时效是多久？` | Missed exact label `merchant_dispute_faq_002`; top-5 includes dispute/time-limit evidence such as `merchant_dispute_faq_005`, `cross_border_refund_004`, `merchant_faq_005`, and `refund_time_limits_002`. | Expected chunk appears at diagnostic rank 10. |

EVAL-02 is closed by the official exact chunk-ID Hit@5 gate because live Hit@5 is at least 80% and fallback accuracy remains at least 80%. The residual misses are retained as audit evidence rather than hidden by label changes.

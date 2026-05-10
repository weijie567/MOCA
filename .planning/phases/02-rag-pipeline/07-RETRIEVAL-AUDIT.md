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

Pending Task 4 live re-ingestion and eval.

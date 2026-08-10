# RAG Format Parity Baseline

Canonical schema: `rag_format_parity_report.v1`
Outcome: `completed_quality_fail`
Baseline eligible: `true`
Generated at: `2026-08-10T13:39:04.921186Z`
Target profile: `rag_format_parity_targets.v1`

Provider reproducibility records exact inputs/config/toolchain and attributable observations; it does not promise bit-identical scores across live runs.

## Identity and configuration

- Manifest SHA-256: `e5544b20ecdf05c2eaf3325b4e5f89a4ef752c0b8c0d23b8bac224f006fdd53b`
- Gold SHA-256: `c6dc12536270fa9b9532ec4595e0a91d2b4ebddf83754a0f1ec107caabb64b8e`
- Dataset baseline identity: `3b1ddd8c19f8fce0a37ad113f3d1161039c200e39e60ce0f2e4d0917d870e110`
- Configured baseline identity: `f2e73bb9dcb339e58d3eb69d696406623b25b526ba66b164cda74666b23a011f`
- Execution kind: `full_provider`
- Command: `TMPDIR_MODE=explicit_macos_private_tmp scripts/eval_rag_format_parity.py --mode full-provider --manifest evaluation/rag_sources/format_parity_manifest.jsonl --gold evaluation/golden/rag_format_parity_gold.json --tenant-id 64300000-0000-4000-8000-000000000001 --owner-marker moca.rag_format_parity.v1 --run-token 64f30400-0000-4000-8000-000000000006 --expected-rollout-version 1`
- Embedding: `dashscope/text-embedding-v4` (1024)
- Retrieval: `retrieval.v3`
- RRF: `rrf_k=60;dense=25;sparse=50;fuzzy=20`
- Rewrite: `query_rewrite.v1:enabled`
- Reranker: `rerank.v2:enabled`
- OCR temp directory mode: `explicit_macos_private_tmp`
- Rollout version: `1`
- Counts: policies=3; fixtures=9; parser_variants=9; retrieval_rounds=3; retrieval_cases=54
- Timings (ms): parser=47084.786; retrieval=79779.512; total=127056.460
- Embedding tokens: `unavailable` (unavailable)

## Gates

| Metric | Operator | Target | Observed | Status |
| --- | --- | ---: | ---: | --- |
| parse_success_rate | >= | 1.000000 | 0.666667 | FAIL |
| markdown_anchor_coverage | >= | 1.000000 | 1.000000 | PASS |
| digital_pdf_anchor_coverage | >= | 1.000000 | 0.314286 | FAIL |
| scanned_pdf_anchor_coverage | >= | 0.950000 | 0.742857 | FAIL |
| critical_table_preservation | >= | 1.000000 | 0.333333 | FAIL |
| pdf_locator_coverage | >= | 1.000000 | 0.528571 | FAIL |
| retrieval_hit_at_5 | >= | 0.900000 | 0.977778 | PASS |
| cross_format_hit_at_5_spread | <= | 0.100000 | 0.066667 | PASS |

## Retrieval metrics

| Slice | Hit@1 | Hit@3 | Hit@5 | MRR | Anchor | No-answer | Fallback | Locator |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 0.844444 | 0.911111 | 0.977778 | 0.894444 | 0.200000 | 0.111111 | 0.851852 | 1.000000 |
| format:markdown | 0.866667 | 0.933333 | 1.000000 | 0.916667 | 0.600000 | 0.000000 | 0.833333 | 1.000000 |
| format:digital_pdf | 0.800000 | 0.933333 | 1.000000 | 0.883333 | 0.000000 | 0.333333 | 0.888889 | 1.000000 |
| format:scanned_pdf | 0.866667 | 0.866667 | 0.933333 | 0.883333 | 0.000000 | 0.000000 | 0.833333 | 1.000000 |
| policy:eval_cross_border_and_digital_goods | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.212121 | 0.333333 | 0.888889 | 0.000000 |
| policy:eval_quality_compensation_and_approval | 0.933333 | 0.933333 | 1.000000 | 0.950000 | 0.233333 | 0.000000 | 0.833333 | 0.000000 |
| policy:eval_refund_eligibility_and_return | 0.600000 | 0.800000 | 0.933333 | 0.733333 | 0.148148 | 0.000000 | 0.833333 | 1.000000 |
| case:cross-case-digital-table | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 1.000000 | 0.000000 |
| case:cross-case-fee-and-digital-state | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.250000 | 0.000000 | 1.000000 | 0.000000 |
| case:cross-case-logistics-exception | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.333333 | 0.000000 | 1.000000 | 0.000000 |
| case:cross-case-no-answer-country-tax-rate | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.333333 | 0.333333 | 0.000000 |
| case:cross-case-order-types | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.166667 | 0.000000 | 1.000000 | 0.000000 |
| case:cross-case-response-and-approval | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.333333 | 0.000000 | 1.000000 | 0.000000 |
| case:quality-case-custom-exception | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.333333 | 0.000000 | 1.000000 | 0.000000 |
| case:quality-case-evidence-and-approval | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.333333 | 0.000000 | 1.000000 | 0.000000 |
| case:quality-case-levels | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.166667 | 0.000000 | 1.000000 | 0.000000 |
| case:quality-case-no-answer-warranty-phone | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| case:quality-case-remedy-table | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 1.000000 | 0.000000 |
| case:quality-case-time-and-percentage | 0.666667 | 0.666667 | 1.000000 | 0.750000 | 0.333333 | 0.000000 | 1.000000 | 0.000000 |
| case:refund-case-decision-priority | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.333333 | 0.000000 | 1.000000 | 0.000000 |
| case:refund-case-missing-accessory-table | 0.000000 | 0.333333 | 0.666667 | 0.250000 | 0.000000 | 0.000000 | 1.000000 | 0.000000 |
| case:refund-case-no-answer-installation | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| case:refund-case-seven-day-exception | 0.666667 | 1.000000 | 1.000000 | 0.833333 | 0.333333 | 0.000000 | 1.000000 | 0.000000 |
| case:refund-case-shipped-auto-review | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.111111 | 0.000000 | 1.000000 | 0.000000 |
| case:refund-case-time-limits | 0.333333 | 0.666667 | 1.000000 | 0.583333 | 0.166667 | 0.000000 | 1.000000 | 1.000000 |

## Failure attribution

| Policy | Format | Case | Primary stage | Reason codes |
| --- | --- | --- | --- | --- |
| eval_cross_border_and_digital_goods | markdown | cross-case-digital-table | chunking | retrieved_evidence_anchor_missing |
| eval_cross_border_and_digital_goods | markdown | cross-case-fee-and-digital-state | chunking | retrieved_evidence_anchor_missing |
| eval_cross_border_and_digital_goods | markdown | cross-case-no-answer-country-tax-rate | retrieval | no_answer_fallback_incorrect |
| eval_cross_border_and_digital_goods | markdown | cross-case-order-types | chunking | retrieved_evidence_anchor_missing |
| eval_cross_border_and_digital_goods | digital_pdf | cross-case-digital-table | chunking | retrieved_evidence_anchor_missing |
| eval_cross_border_and_digital_goods | digital_pdf | cross-case-fee-and-digital-state | parser | semantic_anchor_missing |
| eval_cross_border_and_digital_goods | digital_pdf | cross-case-logistics-exception | parser | semantic_anchor_missing |
| eval_cross_border_and_digital_goods | digital_pdf | cross-case-order-types | parser | semantic_anchor_missing |
| eval_cross_border_and_digital_goods | digital_pdf | cross-case-response-and-approval | parser | semantic_anchor_missing |
| eval_cross_border_and_digital_goods | scanned_pdf | cross-case-digital-table | chunking | retrieved_evidence_anchor_missing |
| eval_cross_border_and_digital_goods | scanned_pdf | cross-case-fee-and-digital-state | ocr | semantic_anchor_missing |
| eval_cross_border_and_digital_goods | scanned_pdf | cross-case-logistics-exception | chunking | retrieved_evidence_anchor_missing |
| eval_cross_border_and_digital_goods | scanned_pdf | cross-case-no-answer-country-tax-rate | retrieval | no_answer_fallback_incorrect |
| eval_cross_border_and_digital_goods | scanned_pdf | cross-case-order-types | ocr | semantic_anchor_missing |
| eval_cross_border_and_digital_goods | scanned_pdf | cross-case-response-and-approval | chunking | retrieved_evidence_anchor_missing |
| eval_quality_compensation_and_approval | markdown | quality-case-levels | chunking | retrieved_evidence_anchor_missing |
| eval_quality_compensation_and_approval | markdown | quality-case-no-answer-warranty-phone | retrieval | no_answer_fallback_incorrect |
| eval_quality_compensation_and_approval | markdown | quality-case-remedy-table | chunking | retrieved_evidence_anchor_missing |
| eval_quality_compensation_and_approval | digital_pdf | quality-case-custom-exception | parser | semantic_anchor_missing |
| eval_quality_compensation_and_approval | digital_pdf | quality-case-evidence-and-approval | parser | semantic_anchor_missing |
| eval_quality_compensation_and_approval | digital_pdf | quality-case-levels | parser | semantic_anchor_missing |
| eval_quality_compensation_and_approval | digital_pdf | quality-case-no-answer-warranty-phone | retrieval | no_answer_fallback_incorrect |
| eval_quality_compensation_and_approval | digital_pdf | quality-case-remedy-table | chunking | retrieved_evidence_anchor_missing |
| eval_quality_compensation_and_approval | digital_pdf | quality-case-time-and-percentage | parser | semantic_anchor_missing |
| eval_quality_compensation_and_approval | scanned_pdf | quality-case-custom-exception | chunking | retrieved_evidence_anchor_missing |
| eval_quality_compensation_and_approval | scanned_pdf | quality-case-evidence-and-approval | ocr | semantic_anchor_missing |
| eval_quality_compensation_and_approval | scanned_pdf | quality-case-levels | ocr | semantic_anchor_missing |
| eval_quality_compensation_and_approval | scanned_pdf | quality-case-no-answer-warranty-phone | retrieval | no_answer_fallback_incorrect |
| eval_quality_compensation_and_approval | scanned_pdf | quality-case-remedy-table | ocr | semantic_anchor_missing |
| eval_quality_compensation_and_approval | scanned_pdf | quality-case-time-and-percentage | ocr | semantic_anchor_missing |
| eval_refund_eligibility_and_return | markdown | refund-case-missing-accessory-table | chunking | retrieved_evidence_anchor_missing |
| eval_refund_eligibility_and_return | markdown | refund-case-no-answer-installation | retrieval | no_answer_fallback_incorrect |
| eval_refund_eligibility_and_return | markdown | refund-case-shipped-auto-review | chunking | retrieved_evidence_anchor_missing |
| eval_refund_eligibility_and_return | markdown | refund-case-time-limits | chunking | retrieved_evidence_anchor_missing |
| eval_refund_eligibility_and_return | digital_pdf | refund-case-decision-priority | parser | semantic_anchor_missing |
| eval_refund_eligibility_and_return | digital_pdf | refund-case-missing-accessory-table | chunking | retrieved_evidence_anchor_missing |
| eval_refund_eligibility_and_return | digital_pdf | refund-case-no-answer-installation | retrieval | no_answer_fallback_incorrect |
| eval_refund_eligibility_and_return | digital_pdf | refund-case-seven-day-exception | parser | semantic_anchor_missing |
| eval_refund_eligibility_and_return | digital_pdf | refund-case-shipped-auto-review | parser | semantic_anchor_missing |
| eval_refund_eligibility_and_return | digital_pdf | refund-case-time-limits | parser | semantic_anchor_missing |
| eval_refund_eligibility_and_return | scanned_pdf | refund-case-decision-priority | ocr | semantic_anchor_missing |
| eval_refund_eligibility_and_return | scanned_pdf | refund-case-missing-accessory-table | ocr | semantic_anchor_missing |
| eval_refund_eligibility_and_return | scanned_pdf | refund-case-no-answer-installation | retrieval | no_answer_fallback_incorrect |
| eval_refund_eligibility_and_return | scanned_pdf | refund-case-seven-day-exception | ocr | semantic_anchor_missing |
| eval_refund_eligibility_and_return | scanned_pdf | refund-case-shipped-auto-review | chunking | retrieved_evidence_anchor_missing |
| eval_refund_eligibility_and_return | scanned_pdf | refund-case-time-limits | chunking | retrieved_evidence_anchor_missing |

## Prerequisites

| Name | Status | Reason | Version |
| --- | --- | --- | --- |
| embedding_provider | available | prerequisite_available | n/a |
| ocr_runtime | available | ocr_runtime_available | 5.5.2 |
| persistence | not_required | parser_direct_has_no_persistence_dependency | n/a |
| postgresql_pgvector | available | prerequisite_available | n/a |
| retrieval_runtime | not_required | parser_direct_has_no_retrieval_dependency | n/a |
| tesseract_chi_sim_eng | available | prerequisite_available | n/a |

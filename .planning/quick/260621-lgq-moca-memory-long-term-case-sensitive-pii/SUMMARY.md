---
status: complete
quick_id: 260621-lgq
slug: moca-memory-long-term-case-sensitive-pii
completed_at: "2026-06-21T15:39:00+08:00"
---

# Quick Task 260621-lgq Summary

## Completed

- Added a shared prompt-facing memory PII policy and applied it to session, long-term, and case memory write/retrieval paths.
- Blocked `sensitive` and `prohibited` long-term/case memory candidates before durable writes.
- Filtered prompt-facing long-term/case retrieval to only `none` and `low` PII classifications.
- Added active case memory duplicate detection for content hash and source identity hash.
- Added `/api/v1/memory` review endpoints for pending list plus approve/reject/delete/forget actions for long-term and case memory.
- Updated graph reviewed case memory retrieval to require a current query before calling case memory search.

## Verification

```bash
uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/agent/test_graph.py tests/test_memory_review_api.py
```

Result: `53 passed, 20 warnings`.

## Notes

- Direct `pytest` still resolves to a Python 3.9 user install in this shell; recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Items 5 and 6 remain intentionally deferred for follow-up discussion.

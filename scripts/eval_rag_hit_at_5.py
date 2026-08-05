"""Deprecated compatibility entry point for the canonical RAG evaluator.

Use ``uv run python scripts/eval_rag.py`` for new integrations. This module
keeps the legacy filename importable while delegating all behavior, defaults,
and report generation to :mod:`scripts.eval_rag`.
"""

from __future__ import annotations

import asyncio
import warnings

from scripts.eval_rag import (
    DEFAULT_GOLDEN_SET,
    DEFAULT_OUTPUT,
    DEFAULT_THRESHOLD,
    _build_report,
    _finalize_category_rates,
    _load_cases,
    _parser,
    _print_report,
    _ranked_evidence,
    _record_category,
    _score_case,
    _search_policy,
    main,
    resolve_tenant_id,
    run_rag_eval,
)

__all__ = [
    "DEFAULT_GOLDEN_SET",
    "DEFAULT_OUTPUT",
    "DEFAULT_THRESHOLD",
    "_build_report",
    "_finalize_category_rates",
    "_load_cases",
    "_parser",
    "_print_report",
    "_ranked_evidence",
    "_record_category",
    "_score_case",
    "_search_policy",
    "main",
    "resolve_tenant_id",
    "run_rag_eval",
]


def _run_legacy_entrypoint() -> None:
    warnings.warn(
        "scripts/eval_rag_hit_at_5.py is deprecated; use scripts/eval_rag.py",
        FutureWarning,
        stacklevel=2,
    )
    asyncio.run(main())


if __name__ == "__main__":
    _run_legacy_entrypoint()

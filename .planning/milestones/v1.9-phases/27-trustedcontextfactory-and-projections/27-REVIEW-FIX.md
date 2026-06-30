# Phase 27 Code Review Fix

## 来源

GSD code review: `.planning/phases/27-trustedcontextfactory-and-projections/27-REVIEW.md`

## 裁决

- WR-01 成立。`MerchantScopeV1` 支持 `categories` / `risk_levels` 限制，但当前 `KnowledgeContext` 只能表达 merchant id list。如果把 `merchant_ids=["*"]` 且带 category/risk 限制的 canonical scope 投影成 `["*"]`，会在 knowledge service 边界放大授权范围，违反 APF-04 no-widening 要求。

## 修复

- `src/platform/context_projections.py`
  - `project_merchant_scope_for_knowledge(...)` 对带 `categories` 或 `risk_levels` 的结构化 scope fail closed，返回空 list。
  - dict 输入先用 `MerchantScopeV1` 校验，再走同一个 fail-closed 逻辑。

- `tests/platform/test_context_projections.py`
  - 新增 `test_knowledge_projection_fails_closed_for_restrictive_scope_dimensions`。
  - 覆盖 canonical `TrustedContext -> KnowledgeContext` 和 `ToolCallContext -> KnowledgeContext` 两条投影路径。

## 回归

- `uv run pytest tests/platform/test_context_projections.py -q`
- `uv run ruff check src/platform/context_projections.py tests/platform/test_context_projections.py`

# Phase 64.2 Deferred Items

## 2026-08-06 — Full-suite 既有非阻塞 warnings

- LangGraph 对 `src/agent/graph.py` 两个 node 的 `config` annotation 发出重复 `UserWarning`；本轮未修改 graph typing，留给后续独立维护。
- `tests/knowledge/test_facade_integration.py` 四项用例触发 `AsyncMockMixin._execute_mock_call was never awaited`；full suite 仍为绿色，且与本轮 evidence/memory fixture 迁移无直接因果，需后续单独核对 mock 生命周期。
- Alembic `path_separator` deprecation、LangChain serializer pending deprecation 为既有工具链告警；本 phase 不改依赖或全局配置。

证据：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest --lf -q --tb=short` 在 lastfailed 清空后执行完整套件，结果为 `4455 passed, 4 skipped, 152 warnings in 1993.29s`。

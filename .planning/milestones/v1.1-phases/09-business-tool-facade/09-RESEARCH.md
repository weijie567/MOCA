# Phase 9: Business Tool Facade — Research

**Researched:** 2026-06-12
**Phase goal:** Route read business tools through `BusinessToolService` using trusted `ToolCallContext` and typed `ToolResultV2`.
**Requirements:** TOOL-01, TOOL-02, TOOL-03
**Question answered:** "What do I need to know to PLAN this phase well?"

> Method note: all findings below are grounded in the current repo (source files, contract-spec sections, requirements) read on 2026-06-12. Section/line citations use contract-spec section numbers per the canonical-refs rule. "Confirmed" = read in code/spec; "Not found" = searched and absent.

---

## 1. What Phase 9 must deliver (scope, backward from goal + success criteria)

ROADMAP success criteria (verbatim source: `gsd-sdk roadmap.get-phase 9`):
1. Read tools use the facade without exposing raw invalid upstream payloads.
2. Permission, scope, status, timeout, partial-success, and invalid-response contracts pass.
3. Write/action execution remains outside this facade.

Requirements (`.planning/REQUIREMENTS.md:15-17`):
- **TOOL-01**: Read business tools use BusinessToolService and trusted ToolCallContext.
- **TOOL-02**: ToolResultV2 covers permission/scope/status/timeout/partial/invalid-response behavior without raw invalid payload exposure.
- **TOOL-03**: Write/action tools remain outside the read-tool facade.

Migration §19 Phase 9 row (`docs/migration-plan.md:15`) — deliverables, exit criteria, rollback:
- Deliverables: `src/business_tools/service.py`, contracts, demo adapters; `ToolCallContext`/`ToolResult` v2; `ToolRegistry`/`ToolDescriptor` (§12.6, single declaration/dispatch/validation entry, read/retrieval/write full declaration).
- Exit criteria: permission/scope; not_found; timeout; partial_success; invalid_response.
- Read-switch: read tools uniformly go through BusinessToolService; nodes do not directly touch repo/tool internals.
- Rollback: per-node call rollback-able; no write actions implemented.

**Backward-derived must-build list:**
- A) `ToolCallContext` (`tool_context.v2`) — 18-field trusted context, system-injected.
- B) `ToolResultV2` (`tool_result.v2`) — 10-status typed result envelope + `ToolError` + `BusinessFactRefV1` + `ToolRequest`.
- C) `BusinessContextV1` (`business_context.v1`) — aggregated output of `fetch_context`.
- D) `ToolRegistry` + `ToolDescriptor` (§12.6) — single declaration/dispatch/validation entry; declares read/retrieval/write.
- E) `BusinessToolService` facade — `fetch_context(slots, intent, ctx) -> BusinessContextV1` and `invoke_tool(name, args, ctx) -> ToolResultV2`.
- F) Adapter layer reuse — map existing `get_order/get_refund_case/get_ticket` raw `{status,data,error}` into `ToolResultV2`, populating `business_fact_refs`.
- G) Migrate the direct-call node `load_business_context` to consume the facade (read-switch); keep rollback seam.
- H) Contract tests for permission/scope (deny-all, unknown-category, no-widening), not_found, timeout, partial_success, invalid_response, and "no raw invalid payload exposure".

---

## 2. Current repo facts (what exists, what must change)

### 2.1 Existing prior-line tool code (CONTEXT-locked relationship)

| File | State | Phase 9 disposition |
| --- | --- | --- |
| `src/agent/tools/registry.py` | `ToolRegistry` with `INVESTIGATOR_TOOL_NAMES` whitelist, `allowed_in_investigator`, 2-state `ToolExecutionResult`, `_evidence_refs_from_data` (policy chunks) | **Replace.** Drop investigator whitelist semantics; replace result type; remove policy evidence extraction from business path. |
| `src/agent/tools/contracts.py` | `ToolInvocationContext` (5 fields), `ToolExecutionResult` (success/error), `ToolEvidenceRef` | **Replace** with v2 contracts (`ToolCallContext`, `ToolResultV2`, `ToolError`, `BusinessFactRefV1`). |
| `src/agent/tools/adapters.py` | `get_order_adapter/get_refund_case_adapter/get_ticket_adapter/search_policy_adapter` + input schemas | **Reuse** the three business adapters + input schemas + tenant-scoped fetch. `search_policy_adapter` belongs to Phase 8 KnowledgeService — do NOT re-own. |
| `src/agent/tools/get_order.py` / `get_refund_case.py` / `get_ticket.py` | Concrete read tools, raw `{status, data, error}` dicts, error codes `VALIDATION_ERROR/ORDER_NOT_FOUND/FORBIDDEN/DB_TIMEOUT/DB_ERROR`, 10s `asyncio.wait_for` timeout | **Reuse as adapter impl.** These are the raw layer the facade normalizes into `ToolResultV2`. |
| `src/agent/tools/authz.py` | `merchant_can_access`, `order_merchant_id` | **Reuse** for scope checks. |
| `src/agent/tools/search_policy.py` | Policy retrieval | **Do NOT own** — Phase 8 territory. |
| `src/agent/tools/create_coupon_grant_draft.py` | Write tool (draft) | **Declare-only** in registry (see Decision D2); never executed via `invoke_tool`. |
| `tests/agent/test_tools/test_registry.py`, `test_tool_contracts.py`, `test_tool_adapters.py` | Tests bound to old contracts (`ToolInvocationContext`, `ToolRegistryEntry`, `ToolOutput`) | **Rewrite** to v2 contracts. |

### 2.2 The direct-call node to migrate (read-switch target)

`src/agent/nodes/load_business_context.py` (confirmed):
- Imports and calls `get_order/get_refund_case/get_ticket` **directly** (lines 9-11, 52/60/68) — bypasses the registry entirely.
- Reads `session` from `config["configurable"]`, identity from `state` (`tenant_id/user_id/role`).
- Conditional load: `intent in {refund_troubleshooting, compensation_suggestion}` OR has a current identifier slot.
- Writes `business_context`, `tool_results`, `last_business_context_refs`, `trace_steps`.
- **This is the live read path the spec's §8 producer-annotation gap refers to: "main graph nodes still call concrete tool functions directly, not through BusinessToolService."**

Graph wiring (confirmed `src/agent/graph.py:62,73,74`):
- Node id `load_business_context`; edges `extract_slots -> load_business_context -> retrieve_policy_evidence`.
- `investigate.py` does **NOT** exist yet (Phase 10 not executed). The §9.4 `investigate` node is target-state; current graph uses the older `load_business_context` + `retrieve_policy_evidence` split.

### 2.3 Contracts already in code (reuse, do not redefine)

- `src/knowledge/schemas.py` (Phase 8): `EvidenceRefV1` (`evidence_ref.v1`), `KnowledgeContext`. **`ToolResultV2.policy_evidence_refs` must import this canonical `EvidenceRefV1`** — do not define a reduced variant (§8 producer rule, §12.5 rule).
- **`TrustedContext` / `MerchantScopeV1` canonical classes: NOT FOUND in `src/`** (searched 2026-06-12). Phase 8's `KnowledgeContext` inlines `merchant_scope: list[str] | None` rather than projecting a canonical class. → **Spec Consistency Finding SCF-1** (§4).

---

## 3. Contracts to implement (exact shapes from contract-spec §8 / §12.5 / §12.6)

These are normative. Copy field-for-field; do not widen identity/scope fields (they are §8.0 TrustedContext projections).

### 3.1 `ToolCallContext` (`tool_context.v2`, §12.5 lines 938-956)
18 fields. **Copy the EXACT types and defaults from §12.5 (do not borrow Phase 8's `KnowledgeContext` shape).** Normative field types:
- `schema_version: Literal["tool_context.v2"] = "tool_context.v2"`
- `tenant_id: str`, `user_id: str`, `role: str` (required)
- `permissions: list[str]` (required)
- `merchant_scope: dict[str, Any]` — **REQUIRED `dict`, NOT `list[str] | None`.** §8.0 freezes it as structured `MerchantScopeV1` (`merchant_ids`/`categories`/`risk_levels`/`match_rule`). Phase 9 carries it as `dict[str, Any]` per §12.5 (the canonical `MerchantScopeV1` class is SCF-1 deferred to Phase 10, but the dict MUST preserve the categories/risk_levels dimensions so unknown-category scope checks are expressible).
- `session_id: str | None = None` (**optional, nullable** — §8.0 line 21)
- `thread_id: str`, `run_id: str`, `trace_id: str` (required)
- `request_id: str`, `tool_call_id: str`, `caller_node: str` (required)
- `deadline_at: datetime | None = None`
- `attempt: int = 1`
- `max_attempts: int = 1`
- `idempotency_key: str | None = None`
- `policy_snapshot_ref: str | None = None`

All system-injected; never LLM/user-generated. **Preserve every `= None` / `= False` default exactly — do not make spec-optional fields required-at-construction.**

### 3.2 `ToolResultV2` (`tool_result.v2`, §12.5 lines 965-989)
10 statuses: `success | partial_success | not_found | permission_denied | timeout | unavailable | conflict | invalid_request | invalid_response | error`. Fields (preserve §12.5 defaults EXACTLY): `data: dict|None, summary: str, source_system: str, data_freshness_at: datetime|None, policy_evidence_refs: list[EvidenceRefV1] = [] (business tools leave empty), business_fact_refs: list[BusinessFactRefV1] = [], error: ToolError | None = None, retryable: bool = False, retry_after_ms: int | None = None, latency_ms: int (REQUIRED, no default), audit_ref: str | None = None`.

### 3.3 `ToolError` (§12.5 991-995)
`code: str, safe_message: str, retryable: bool, source: Literal["caller","tool","adapter","upstream","policy"]`.

### 3.4 `BusinessFactRefV1` (`business_fact_ref.v1`, §12.5 997-1005)
`tenant_id, source_system, resource_type: Literal["order","refund_case","ticket","logistics","merchant_risk"], resource_id, resource_version: str|None, data_freshness_at: datetime|None, retrieved_at: datetime`. **Not assignable to `EvidenceRefV1`** (§12.5 rule 1012).

### 3.5 `ToolRequest` (`tool_request.v2`, §12.5 958-963)
`tool_name, arguments: dict, argument_hash: str, redaction_policy_version: str`.

### 3.6 `BusinessContextV1` (`business_context.v1`, §8.4 172-182)
`tenant_id, status: Literal["complete","partial","insufficient","error"], facts: dict, business_fact_refs: list[BusinessFactRefV1], tool_results: list[ToolResultV2], missing_required_facts: list[str], errors: list[ToolError], data_freshness_at: datetime|None`. Must NOT include policy `EvidenceRefV1`.

### 3.7 `ToolDescriptor` + `ToolRegistry` (§12.6 1031-1044)
`ToolDescriptor`: `name, kind: read|retrieval|write, input_schema: dict, output_schema: dict (for ToolResultV2.data), risk_level, side_effect, required_permission (e.g. "tool:get_order"), caller_allowlist: list[str], event_family: Literal["tool_call_*","rag_retrieval_*"], resource_type: str|None`.
`ToolRegistry.invoke(name, input_data, ctx) -> ToolResultV2` — resolve descriptor → check `caller_node` allowlist → check `required_permission` → validate `input_schema` → run adapter → validate adapter output against `output_schema` → adapt to `ToolResultV2`.

### 3.8 `investigate` allowlist descriptors (§12.6 table 1058-1067)
Read (`tool_call_*`): `get_order`(order), `get_refund_case`(refund_case), `get_ticket`(ticket), `get_logistics`(logistics), `get_merchant_risk`(merchant_risk). Retrieval (`rag_retrieval_*`, resource_type null): `search_policy`, `search_sop`, `search_case_memory`.
- `caller_allowlist` MUST use the merged node name `investigate`, NOT `load_business_context`/`retrieve_policy_evidence` (§12.6 rule 1050). → see SCF-2.
- `get_logistics`/`get_merchant_risk` have no repo backing yet → **register-but-unavailable** (return `ToolResultV2(status="unavailable")`), per 10-04 loop-facing contract.

### 3.9 Status-mapping seam (raw tool → ToolResultV2)
The raw error codes in `get_order.py` etc. map deterministically (per 10-04 loop-facing contract minimum + §12.5):
| Raw error_code | ToolResultV2.status | ToolError.source |
| --- | --- | --- |
| (success) | `success` | — |
| `FORBIDDEN` | `permission_denied` | `caller`/`policy` |
| `ORDER_NOT_FOUND` (and refund/ticket equivalents) | `not_found` | `upstream` |
| `DB_TIMEOUT` | `timeout` | `adapter` |
| `VALIDATION_ERROR` (bad input) | `invalid_request` | `caller` |
| adapter output fails `output_schema` validation | `invalid_response` | `adapter` |
| `DB_ERROR`/other | `error` / `unavailable` | `adapter`/`upstream` |
`invalid_response` and raw payloads MUST NOT leak: graph nodes consume typed `data`/`summary`/refs/status only (§12.5 1021-1022). This is the TOOL-02 "no raw invalid payload exposure" criterion.

---

## 4. Spec Consistency Findings (MANDATORY per migration-plan §19 line 59/64)

Use the Deviation Handling Protocol (`docs/agent-architecture-phase-decomposition.md` Section 1). These MUST be carried into the PLAN.md `Spec Consistency Findings` block. Not pre-resolved — surfaced for the planner/executor to honor.

| ID | Source requirement | Conflicting evidence | Type | Recommended handling | Readiness impact | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **SCF-1** | §8.0 declares canonical `TrustedContext`/`MerchantScopeV1` as Phase 7 shared contract; §12.5 says `ToolCallContext` identity/scope fields are projections of it | No `TrustedContext`/`MerchantScopeV1` class in `src/` (searched 2026-06-12); Phase 8 `KnowledgeContext` inlines `merchant_scope: list[str]|None` | Missing upstream contract | `ToolCallContext` defines the 9 identity/scope fields inline with §8.0 semantics (no widening/rename); §8.0 line 50 explicitly defers convergence-to-single-TrustedContext-source to Phase 10. Do NOT block Phase 9 on a missing Phase 7 class. | Phase 9 proceeds; Phase 10 owns convergence | Phase 10 | OPEN |
| **SCF-2** | §12.6 rule (1050): `caller_allowlist` MUST use merged node name `investigate`, never `load_business_context`/`retrieve_policy_evidence` | Current graph still has `load_business_context` node (graph.py:62); `investigate` node does not exist (Phase 10 unbuilt) | Naming/sequencing mismatch | Registry descriptors declare `caller_allowlist=["investigate"]` per spec (forward-correct). The read-switch migrates `load_business_context` to call `BusinessToolService.fetch_context`; the facade does NOT gate on `caller_node=="load_business_context"`. Document that until Phase 10 lands, the node calling the facade is `load_business_context` but the registry allowlist is the canonical `investigate`. Decide caller_node value injected at the migrated node (see Decision D4). | Phase 9 facade works pre-Phase-10; allowlist forward-correct | Phase 9 (facade) / Phase 10 (node rename) | OPEN |
| **SCF-3** | §19 (15): registry declares read/retrieval/**write** full set | §12.6 rule (1053): `ToolDescriptor.event_family` enum is only `tool_call_*|rag_retrieval_*`, no `action_*`; spec explicitly "留 Phase 9 决策" | Spec under-specified | **Decision D2 (user-confirmed):** declare write tool (`create_coupon_grant_draft`) descriptor for permission/schema unification, hard-block execution via `invoke_tool`/investigate; defer `action_*` event_family to Phase 17. Record as deviation: write descriptor's `event_family` left unset/sentinel pending §17. | Registry is full-declaration per §19; execution path unaffected | Phase 17 (event family) | RESOLVED (deferred) |
| **SCF-4** | §12.5 (1017): every tool call must write a replay event or audit_ref | Phase 10c owns "minimal event emitter/allocator/base table" (§19 line 16); no event infra in Phase 9 | Sequencing | **Decision D3 (user-confirmed):** facade does not introduce its own audit/persistence table; `ToolResultV2.audit_ref` left `None`; tool-call event emission is a seam consumed by Phase 10c. CONTEXT facade-persistence question → recorded `N/A` for Phase 9. | No new migration in Phase 9; rollback simple | Phase 10c | RESOLVED (deferred) |
| **SCF-5** | §12.5 `ToolCallContext` is a serializable trusted projection with `session_id: str`; §8.4 `BusinessToolService.fetch_context(slots, intent, ctx)` signature carries no DB handle | Live read path needs an `AsyncSession`: today `load_business_context` pulls `session` from `config["configurable"]["session"]` (graph.py/router inject the live `AsyncSession`) and passes it to `get_order(...)`. `ToolCallContext` cannot carry an `AsyncSession` (it is a typed trusted projection, must stay serializable, §12.5). | Contract-vs-runtime gap | **Decision D8 (user-confirmed):** keep `ToolCallContext` pure (`session_id: str` only, no DB handle). `AsyncSession` is a runtime dependency injected into `BusinessToolService` at construction (e.g. `BusinessToolService(registry, session=...)`) or passed alongside `fetch_context`/`invoke_tool` as an explicit non-context param — NOT smuggled into `ToolCallContext`. The migrated node (09-05) builds the service from `configurable["session"]`. | Facade must own a session-injection seam; otherwise call chain cannot reach raw tools | Phase 9 (09-04 facade ctor / 09-05 node wiring) | OPEN |
| **SCF-6** | §8.0/§12.5 require `permissions` + `merchant_scope` on `ToolCallContext`, constructed in-node from trusted run config (§8.0 line 48-50) | `AgentState` has no `permissions`/`merchant_scope` fields (state.py:52-55 only `thread_id/tenant_id/user_id/role`); `config["configurable"]` injects only `thread_id`+`session` (agent_runs.py:128-131); `trace_id` exists at router level (agent_runs.py:76) but is not in `configurable`. | Missing trusted-context plumbing | **Decision D9:** per §8.0 line 48-50, do NOT add `permissions`/`merchant_scope` to persisted `AgentState`. In 09-05 the router derives permissions from trusted `ROLE_SCOPES[user.role]` (or token payload scopes) through the fixed `orders:read`/`refunds:read`/`tickets:read`/`knowledge:read` → `tool:get_order`/`tool:get_refund_case`/`tool:get_ticket`/`tool:search_policy` bridge, ignores unmapped scopes, and projects merchant role to `{"merchant_ids":[str(user.merchant_id)]}` while non-merchant roles receive explicit wildcard `{"merchant_ids":["*"]}`. Empty derived permissions fail closed. This orders:read→tool:* bridge + merchant_id projection is the Phase 9 concrete derivation; full structured MerchantScopeV1 + richer permission-model convergence remains Phase 10. | 09-05 has a deterministic trusted authorization projection; empty derivation denies | Phase 9 (09-05 + router) / Phase 10 (convergence) | RESOLVED (Phase 9 bridge) |
| **SCF-7** | Migration §19 Phase 9 row: read-switch should be "可回滚单个 node 调用"; existing `tool_results` entries are `{"tool": name, **raw_result}` (load_business_context.py:53/61/69) | `ToolResultV2` has no `tool_name`/`tool` field (§12.5); a faithful read-switch cannot "exactly preserve" the current `tool_results` shape | Downstream-shape mismatch | **Handling:** the legacy `{"tool": name}` key is dropped because no consumer reads it (grep-verified in `src/`); `tool_results` now carries `ToolResultV2` objects. If any future consumer needs the name, reconstruct it from the slot→tool map. | Deliberate migration recorded; rollback remains the node read-switch | Phase 9 (09-05) | RESOLVED (documented migration) |
| **SCF-8** | §12.6:1043 ToolRegistry.invoke 3-arg Protocol | session must be threaded to adapters but cannot enter ToolCallContext (SCF-5) | spec-Protocol vs runtime-dependency | implementation extends invoke to 4-arg (name, input_data, ctx, session); session is an explicit non-context runtime param, not part of the normative tool_context.v2 projection; the §12.6 Protocol's logical 3-arg contract (descriptor resolve→gate→validate→adapt) is preserved, session only carries the DB handle | none, internal | Phase 9 | RESOLVED (documented deviation) |

---

## 5. Key decisions feeding the plan

- **D1 — Module location:** `src/business_tools/` (new package): `schemas.py` (v2 contracts), `registry.py` (`ToolDescriptor`+`ToolRegistry`), `adapters.py` (raw→ToolResultV2 mapping, reusing existing tool fns), `service.py` (`BusinessToolService`). Matches §19 / §8.4 / CONTEXT suggestion. The old `src/agent/tools/` business pieces are superseded; keep `get_order.py` etc. as the raw adapter impl (imported by the new adapter layer) to minimize churn — OR move them. **Open micro-choice for planner:** import-in-place vs relocate (lean import-in-place to keep diff small and rollback easy).
- **D2 — Write tool:** declare-but-deny-execute + defer event family (SCF-3).
- **D3 — Audit/persistence:** no table; audit_ref=None; event seam to Phase 10c (SCF-4).
- **D4 — caller_node at migrated node:** inject `caller_node="investigate"` (canonical) even though the physical node is still `load_business_context`, so the descriptor allowlist (`["investigate"]`) passes and the code is forward-correct for Phase 10. (Alternative: allowlist includes both names transitionally — rejected; spec rule 1050 forbids declaring old names.)
- **D5 — Retry mechanism:** `invoke_tool` owns per-call retry: `attempt` 1→`max_attempts`, same `tool_call_id` across attempts, `attempt > max_attempts` never re-calls (§12.5 1019, 10-04 contract). Loop control (max_iterations/deadline) stays in Phase 10 — facade does NOT implement loop.
- **D6 — `fetch_context` vs `invoke_tool`:** both built. `fetch_context(slots, intent, ctx)` aggregates the conditional read set (mirrors current `load_business_context` logic: order/refund/ticket by slot presence) into `BusinessContextV1`; `invoke_tool` is the single-tool dispatch the Phase 10 loop will call per-iteration. Read-switch wires `load_business_context` to `fetch_context`.
- **D7 — provenance:** business reads populate `business_fact_refs` (BusinessFactRefV1 with tenant_id/source_system/resource_type/resource_id/retrieved_at, data_freshness_at where available); `policy_evidence_refs` stays empty (§12.5 1024). No policy EvidenceRef in business path (drop `_evidence_refs_from_data` for business tools).
- **D9 — live authorization projection:** 09-05 derives tool permissions through the fixed `ROLE_SCOPES` scope→tool-token bridge and projects authenticated User role/merchant_id into merchant_scope; unmapped/empty permissions fail closed. Full MerchantScopeV1/richer-permission convergence remains Phase 10 (SCF-6).

---

## 6. Test strategy (exit-criteria backward)

§19 exit criteria + TOOL-02 demand contract tests. Required cases (these are the verification spine):
- **Permission/scope:** deny-all (empty `merchant_scope` → deny, not unrestricted), unknown-category, no-widening (model-provided merchant id not in scope rejected before adapter). `permissions` unknown token / empty → deny. (§8.0 line 38 mandates these negative cases.)
- **permission_denied:** `FORBIDDEN` from `merchant_can_access` → `ToolResultV2(status="permission_denied")`, no data leak.
- **not_found:** missing order/refund/ticket → `not_found`.
- **timeout:** `asyncio.TimeoutError`/`DB_TIMEOUT` → `timeout`, `retryable=True`.
- **partial_success:** only when result explicitly lists missing/failed subresources in `summary`/`error` (§12.5 1020) — for `fetch_context` aggregating multiple reads where some succeed and some fail.
- **invalid_response:** adapter/upstream returns data failing `output_schema` → `invalid_response`; **raw invalid payload NOT exposed** (assert graph-facing result has no raw upstream dict). This is the headline TOOL-02 case.
- **invalid_request:** bad input args fail `input_schema` → `invalid_request`.
- **registry single-entry consistency:** §12.4 allowlist / §12.5 resource_type enum derivable from registry; adding a tool can't drift multiple lists (§12.6 1028).
- **write-tool block:** `invoke_tool("create_coupon_grant_draft", ...)` → denied/blocked, never executes (TOOL-03).
- **business_fact_refs vs policy_evidence_refs:** business read populates `business_fact_refs`, leaves `policy_evidence_refs` empty; assert `BusinessFactRefV1` not coercible to `EvidenceRefV1`.
- **max_attempts retry:** attempt increments, same tool_call_id, stops at max_attempts.
- **read-switch behavior parity:** migrated `load_business_context` produces equivalent `business_context`/`tool_results` for the existing passing cases (regression guard).

Existing tests to rewrite: `tests/agent/test_tools/test_registry.py`, `test_tool_contracts.py`, `test_tool_adapters.py` (bound to old `ToolInvocationContext`/`ToolExecutionResult`). New tests live under `tests/business_tools/` or extend `tests/agent/test_tools/`.

---

## 7. Recommended plan shape (input to planner — not binding)

Natural wave/dependency structure (greenfield package + replace + migrate):

- **Wave 1 (foundation, parallel-safe):**
  - Plan A: `src/business_tools/schemas.py` — all v2 contracts (ToolCallContext, ToolRequest, ToolResultV2, ToolError, BusinessFactRefV1, BusinessContextV1), importing canonical `EvidenceRefV1` from `src.knowledge.schemas`. + schema contract tests.
- **Wave 2 (depends on A):**
  - Plan B: `src/business_tools/registry.py` — `ToolDescriptor` + `ToolRegistry.invoke` (descriptor resolve → allowlist → permission → input_schema → adapter → output_schema → ToolResultV2). Descriptor table for 8 read/retrieval tools + 1 write declare-only. + registry tests (allowlist, permission deny, write-block, single-entry consistency).
  - Plan C: `src/business_tools/adapters.py` — raw→ToolResultV2 status mapping (§3.9 table), business_fact_refs population, register-but-unavailable for logistics/merchant_risk. Reuses existing `get_order/get_refund_case/get_ticket`. + adapter/status-mapping tests (permission/not_found/timeout/invalid_response/no-raw-leak).
- **Wave 3 (depends on B+C):**
  - Plan D: `src/business_tools/service.py` — `BusinessToolService.invoke_tool` (retry/max_attempts) + `fetch_context` (conditional aggregate → BusinessContextV1). + service tests (partial_success aggregation, retry, fetch_context status).
- **Wave 4 (depends on D — read-switch + cleanup):**
  - Plan E: migrate `src/agent/nodes/load_business_context.py` to call `BusinessToolService.fetch_context`; inject `caller_node="investigate"` + ToolCallContext from trusted state/config; preserve state-write shape + rollback seam. Retire old `src/agent/tools/registry.py`/`contracts.py` business semantics (drop investigator whitelist, ToolExecutionResult, business-path `_evidence_refs_from_data`). Rewrite old tests. + read-switch regression tests.

This is ~5 plans across 4 waves. Planner may merge (e.g. B+C in one wave is already parallel) but should NOT collapse the schema foundation (A) into later waves — everything imports it. Every plan carries the applicable SCF-1..8 findings forward and honors D1-D9.

**must_haves (goal-backward):**
- Read tools (order/refund/ticket) reachable ONLY through `BusinessToolService`; `load_business_context` no longer imports concrete tool fns directly.
- `ToolResultV2` emitted for all per-call outcomes incl. permission_denied/not_found/timeout/partial_success/invalid_response, with no raw invalid payload reaching graph nodes.
- Write tool declared in registry but un-executable via facade.
- `business_fact_refs` populated; `policy_evidence_refs` empty for business reads; canonical `EvidenceRefV1` imported, not redefined.
- Spec Consistency Findings SCF-1..8 recorded in plans.

---

*Phase: 09-business-tool-facade*
*Research completed 2026-06-12 — grounded in repo source + contract-spec §8/§9.4/§12.4/§12.5/§12.6 + migration §19 + 10-04 loop-facing contract*

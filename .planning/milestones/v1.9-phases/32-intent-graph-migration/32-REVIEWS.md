---
phase: 32
reviewers: [claude]
reviewed_at: "2026-06-28T13:04:51Z"
plans_reviewed:
  - 32-01-PLAN.md
  - 32-02-PLAN.md
  - 32-03-PLAN.md
  - 32-04-PLAN.md
  - 32-05-PLAN.md
---

# Cross-AI Plan Review — Phase 32

## Claude Review

## Review Scope Note

I checked the current repo state first: working tree is clean on `main`. I also spot-checked the local plan files for `32-01` and `32-04`; the rest of this review is based on the plan text supplied in the request.

---

# Overall Summary

The five-plan split is well-aligned with Phase 32's intent: compatibility-first graph vocabulary migration, registry-owned deterministic policy, safe trace/API projection, and a final static verification gate. The plan set avoids the biggest architectural trap: renaming runtime graph nodes or pretending Phase 33 RAG/claim behavior is done. The main risks are not direction but execution detail: `32-04` is large and crosses many API/trace/schema surfaces, `slot_resolution_gate` is not consistently represented as a first-class target vocabulary item in `32-01`, and several static checks are brittle enough to fail on harmless formatting or miss semantically equivalent regressions. With a few tightening edits, the plan set should achieve APF-11/APF-12 without scope creep.

**Overall risk: MEDIUM** — the architecture is sound, but the trace/API/merchant-context surface and static guard design need sharper boundaries.

---

# Plan `32-01` — Graph Vocabulary and Projection Helper

## Summary

This is the right first step. It isolates legacy-to-target graph naming into a typed helper before touching runtime graph wiring, which matches the compatibility-first migration goal. The non-runnable treatment of `rag_context_build` and `claim_verify` is especially important and well-scoped. The main gap is that `slot_resolution_gate` itself is not clearly covered as a target node mapping in the initial vocabulary, even though APF-11 explicitly names it.

## Strengths

- Starts with tests and a single typed helper instead of scattered string maps.
- Preserves legacy runtime/debug names in `src/agent/graph.py`.
- Treats `rag_context_build` and `claim_verify` as `deferred_non_runnable`, avoiding Phase 33 scope creep.
- Adds unknown-name passthrough behavior, which helps avoid brittle projection failures.
- Keeps trace/API changes out of this plan, which keeps wave 0 small.

## Concerns

- **HIGH:** APF-11 requires mapping for `slot_resolution_gate`, but the required alias list in Task 1 does not include a node-level target mapping for it. Later plans mention it, but `32-01` is supposed to establish the single vocabulary source.
- **MEDIUM:** `classify_intent:pre_route` -> `safety_pre_route` is useful, but it is not an actual runtime node. The plan should specify where this synthetic semantic step appears, otherwise it may exist only in tests.
- **MEDIUM:** `graph_vocabulary_entry(name, kind=None)` can become ambiguous if the same name appears as both node and router later.
- **LOW:** Unknown names defaulting to status `runtime` may be misread as "known implemented runtime entry". It is safe for passthrough, but the status label is semantically loose.
- **LOW:** Source inspection for absence of `builder.add_node("rag_context_build"` can miss alternate formatting or indirection.

## Suggestions

- Add an explicit vocabulary entry for target `slot_resolution_gate`. Options:
  - `extract_slots` -> `slot_resolution_gate` with a note that it is a compatibility semantic projection; or
  - `slot_resolution_gate` -> `slot_resolution_gate` as `deferred/non-physical` or `compatibility_alias`, depending on intended status.
- Add a field such as `known: bool` or status `unknown_passthrough` rather than labeling unknown names as `runtime`.
- Make `kind` mandatory in production call sites where possible; keep `kind=None` only for diagnostics.
- Add tests for target-name identity lookup:
  - `target_graph_name("contextual_intent_resolve", kind="node") == "contextual_intent_resolve"`
  - same for `session_context_load`, `memory_context_load`, `route_after_slot_resolution`.
- Add one test proving `project_trace_step_for_contract` preserves all original step keys, not only `node`.

## Risk Assessment

**LOW-MEDIUM.** The scope is narrow and well-placed, but the missing `slot_resolution_gate` vocabulary coverage could leave APF-11 partially satisfied only through later ad hoc metadata.

---

# Plan `32-02` — Intent Policy Registry Consumption

## Summary

This plan targets the right APF-12 seam: `IntentPolicyRegistry` becomes the consumed effective-policy surface, while LLM output remains candidate-only. The plan properly keeps legacy route keys and Phase 25 fail-closed behavior. The main risk is that the registry could remain a thin wrapper unless tests prove actual runtime consumers call it.

## Strengths

- Moves effective route, risk, direct-response, and required-slot decisions toward registry APIs.
- Keeps `route_after_intent` legacy edge keys unchanged.
- Preserves raw LLM output in `llm_outputs["intent_classification"]`.
- Explicitly protects approval-like chat, safety-sensitive inputs, low confidence, and ambiguous short replies.
- Includes static guard intent: no direct `DIRECT_RESPONSE_INTENTS`, `INTENT_ROUTE_POLICY`, or `REQUIRED_SLOT_POLICY` in consumer files.

## Concerns

- **MEDIUM:** The registry methods are mostly wrappers over existing constants/helpers. This is acceptable for migration, but tests must prove call-site consumption, not just equal values.
- **MEDIUM:** `resolve_precedence(...)` and `resolve_risk_tier(...)` need explicit behavior for unknown or malformed intent/operation values. Otherwise the registry surface may leak exceptions into fail-closed paths.
- **MEDIUM:** Static source checks can prevent direct constant names but cannot prove equivalent hard-coded branches were not reintroduced.
- **LOW:** Adding module-level `INTENT_POLICY_REGISTRY` / `SLOT_POLICY_REGISTRY` makes monkeypatch testing easy, but it can make future dependency injection harder if not documented.
- **LOW:** The plan says "where practical" for replacing precedence/risk helpers. That phrase weakens APF-12; the acceptance criteria should make the required replacements exact.

## Suggestions

- Make registry-consumption tests behavioral:
  - monkeypatch `routing.INTENT_POLICY_REGISTRY.route_for_intent` and prove `route_after_intent` changes only through that API;
  - monkeypatch `classify_intent.SLOT_POLICY_REGISTRY.required_slots_for` and prove LLM-required slots cannot override it.
- Replace "where practical" with a concrete list of remaining allowed direct helper calls, ideally none in `routing.py` and `classify_intent.py`.
- Add explicit fail-closed tests for:
  - unknown intent;
  - unknown requested operation;
  - registry method exception;
  - malformed risk tier result.
- Ensure `classification_trace` keeps existing keys exactly and only adds fields like `candidate_classification` and `policy_owner`, to avoid breaking trace consumers.

## Risk Assessment

**MEDIUM.** The design is right, but APF-12 depends on consumer tests being strong enough. Static grep alone is not enough.

---

# Plan `32-03` — Slot Policy Gate and Target Router Projection

## Summary

This plan correctly moves required-slot and inherited-slot acceptance into `SlotPolicyRegistry` while preserving `route_after_slots` legacy keys. It addresses the most safety-sensitive part of APF-12: stale, wrong-thread, invalidated, or incompatible inherited slots must clarify instead of silently satisfying required business identifiers. The main risk is that the new slot policy API may duplicate routing semantics and accidentally change edge behavior.

## Strengths

- Preserves current-turn explicit slot precedence.
- Encodes existing trusted session slot checks as named registry decisions with reason codes.
- Keeps `route_after_slots` finite over the existing legacy keys.
- Tests cover stale, wrong-thread, invalidated, intent-incompatible, and trusted same-thread memory cases.
- Avoids a physical graph-node split before the behavior is pinned.

## Concerns

- **HIGH:** `slot_resolution_gate` still risks becoming additive trace metadata rather than a canonical vocabulary entry from `graph_vocabulary.py`. That would weaken "single source for target graph aliases".
- **MEDIUM:** Moving `_trusted_session_slot(...)` semantics into `intent_policy.py` may mix policy definitions with state/metadata validation logic. That is acceptable if intentional, but the boundary should be named as slot policy, not pure intent policy.
- **MEDIUM:** The plan needs exact timestamp/freshness handling details. Staleness tests can become flaky if wall-clock time is read directly.
- **MEDIUM:** `SlotInheritanceDecision` only returns `accepted`, reason, and source. The implementation may still need normalized metadata or diagnostic details to avoid losing why a slot was rejected.
- **LOW:** `policy_qa` no-slot path is called out, but the exact expected route should be pinned in tests.

## Suggestions

- Add `slot_resolution_gate` to `src/agent/graph_vocabulary.py` in `32-01` or explicitly amend `32-03` to update the vocabulary helper, not just trace metrics.
- Keep a clear split:
  - `SlotPolicyRegistry` decides whether metadata is acceptable;
  - `routing.resolve_slots_with_metadata` owns merge order and state extraction.
- Inject or pass current time into staleness logic, or keep using existing deterministic timestamp fields, so tests do not rely on wall-clock timing.
- Add idempotence tests:
  - running slot resolution twice must not resurrect rejected inherited slots;
  - rejected inherited slot metadata must not remain in `active_slot_metadata` as accepted.
- Add a negative test where a current-turn ambiguous/partial identifier does not incorrectly override a trusted complete slot unless existing behavior explicitly allows it.

## Risk Assessment

**MEDIUM.** The safety intent is strong, but the implementation seam is delicate because slot resolution already exists inside routing/extraction. Double-merge or stale-slot resurrection is the main failure mode.

---

# Plan `32-04` — Trace/API Projection and Target Merchant Context Evidence

## Summary

This plan covers required APF-11 projection surfaces and D-13 merchant-context evidence, but it is the largest and riskiest plan. It touches trace summary, SSE payloads, trace API, repository timeline projection, schemas, state reset, AgentRun routing, and authorization regression tests. The security stance is correct: target merchant context is evidence/status only and must not widen access. The plan should be tightened around exact data sources, schema ownership, and response compatibility.

## Strengths

- Keeps persisted `AgentStep.node_name` unchanged.
- Adds target graph projection beside legacy fields rather than replacing them.
- Defines safe `target_merchant_context.v1` statuses.
- Explicitly forbids raw merchant/order/refund/ticket identifiers in target merchant-context evidence.
- Preserves owner/admin-only AgentRun, trace, and replay access.
- Adds negative tests for manager/supervisor-style roles.

## Concerns

- **HIGH:** This plan crosses many surfaces in one wave. A small projection change could break SSE, trace API, replay tests, or Pydantic response models.
- **HIGH:** `resolved` target merchant context rules are underspecified: "last_business_context_refs, business_context, or equivalent graph state" is too broad. Implementers need exact approved fields and ref shape.
- **HIGH:** Adding target merchant context into `AgentState` and resetting it per turn may be correct, but it risks treating projection evidence as runtime authority unless all consumers are clearly forbidden.
- **MEDIUM:** `src/api/schemas/approvals.py` as the home for `TraceResponse` projection should be verified. If schema ownership is wrong, this plan may couple unrelated approval schemas to graph trace projection.
- **MEDIUM:** SSE payload changes can break exact-shape tests or clients if response schemas reject extra fields.
- **MEDIUM:** Static negative scans for forbidden raw IDs in `target_merchant_context` may produce false positives from negative test names or comments.
- **LOW:** `business_fact_ref_count` is likely safe, but it still reveals that business refs exist. That is acceptable for owners/admins, but should not appear on unauthorized error paths.

## Suggestions

- Split this plan internally or as two plan files:
  - `32-04a`: target graph projection in trace/SSE/API;
  - `32-04b`: target merchant context evidence and visibility tests.
- Replace "or equivalent graph state" with an allowlist of exact fields and ref keys that can prove `resolved`.
- Add explicit non-authority tests:
  - `target_merchant_context.status == "resolved"` does not allow a non-owner manager to read a run;
  - changing the status to `resolved` in state does not change `_ensure_can_view_run`.
- Add schema compatibility tests for both:
  - existing legacy fields still present;
  - new fields are optional and bounded.
- Consider deriving `target_merchant_context` at summary/projection time first, and only adding it to `AgentState` if a later step truly needs to pass it between nodes.
- Add an allowlist sanitizer test that feeds raw fields like `merchant_id`, `order_id`, `refund_case_id`, `ticket_id`, and `user_query` and proves none appear in output.

## Risk Assessment

**MEDIUM-HIGH.** The security model is sound, but the plan is broad and touches API contracts. Most risk is accidental response breakage or ambiguous merchant-context proof.

---

# Plan `32-05` — Final Focused Verification and Static Contract

## Summary

This is a useful phase gate. It documents the target mapping, checks no fake Phase 33 behavior was introduced, verifies registry consumption, and protects the MOCA-approved test entrypoint rule. Its static checks are valuable as guardrails, but some are brittle and should not be the only proof.

## Strengths

- Adds an architecture test specifically for Phase 32 invariants.
- Checks no runnable `rag_context_build` or `claim_verify` graph nodes exist.
- Checks direct policy constants are gone from key consumer files.
- Records the target mapping in a Chinese phase artifact with explicit non-scope notes.
- Runs a focused suite spanning graph, intent, slot, memory, trace/API, replay, trusted context, and platform context projections.
- Includes `ruff` and `git diff --check`.

## Concerns

- **MEDIUM:** Static check for `ADMIN_RUN_VISIBILITY_ROLES = {"admin"}` is formatting-sensitive. A harmless change to `frozenset({"admin"})` or multiline formatting would fail.
- **MEDIUM:** Static scans can miss semantic regressions, for example hard-coded route policy under different names.
- **MEDIUM:** The command-line scan for invalid pytest usage needs careful parsing. It should distinguish example text saying "do not run pytest" from actual validation commands.
- **LOW:** `32-MVP-TARGET-MAPPING.md` can drift from `graph_vocabulary.py` unless the static test compares the actual helper entries to the table or at least checks key names.
- **LOW:** The final focused suite is large but reasonable. Runtime cost may be non-trivial, but acceptable for phase gate.

## Suggestions

- Make static authorization checks AST- or behavior-based where practical:
  - assert the imported constant equals `{"admin"}`;
  - test actual 403 behavior for non-owner manager/supervisor roles.
- For plan artifact command checks, scan only code blocks, `<automated>` tags, or lines under "verify"/"validation" headings to reduce false positives.
- Add a test that reads `graph_vocabulary.py` entries and checks every `32-MVP-TARGET-MAPPING.md` required mapping is present.
- Add a final "no Phase 33 success path" behavioral check if any graph vocabulary projection exposes `rag_context_build` or `claim_verify`: they must be non-runnable and not graph-registered.
- Keep `32-05` production files unchanged; if a bug appears in earlier code, fix it in the owning plan area and record it in the summary.

## Risk Assessment

**LOW-MEDIUM.** The gate is valuable. The risk is mostly false positives/false negatives from source scans, not architecture direction.

---

# Cross-Plan Dependency and Scope Review

## What Works Well

- Dependency ordering is mostly correct:
  - `32-01` establishes naming;
  - `32-02` moves intent policy;
  - `32-03` moves slot policy;
  - `32-04` exposes projections and merchant evidence;
  - `32-05` closes with static and focused validation.
- Phase 33 boundaries are repeatedly protected.
- Legacy runtime graph names remain stable.
- Owner/admin-only visibility is explicitly preserved.
- The test strategy covers both happy paths and safety-negative paths.

## Main Cross-Plan Gaps

- **HIGH:** `slot_resolution_gate` should be part of the vocabulary helper, not only later metadata.
- **HIGH:** `32-04` needs exact allowed merchant-context proof sources.
- **MEDIUM:** Registry-consumption proof should be behavioral, not mainly static.
- **MEDIUM:** Static scans should not become the only safety proof.
- **MEDIUM:** Synthetic target nodes like `safety_pre_route` need clear projection semantics, or they become documentation-only entries.

---

# Recommended Amendments Before Execution

1. **Patch `32-01` to include `slot_resolution_gate`.**
   - Add either `extract_slots` -> `slot_resolution_gate` or a clear target identity entry.
   - Add tests for this in `tests/agent/test_graph_vocabulary.py`.

2. **Patch `32-02` acceptance to require behavioral monkeypatch tests.**
   - Static source checks are useful, but APF-12 needs runtime proof that consumers call registry APIs.

3. **Patch `32-03` to test slot resolution idempotence.**
   - This catches double-merge regressions and stale inherited slot resurrection.

4. **Narrow `32-04` merchant proof sources.**
   - Define exact allowed fields and exact ref schema for `resolved`.
   - Remove "or equivalent graph state" unless it is replaced by a named allowlist.

5. **Consider splitting `32-04`.**
   - Trace/API graph projection and merchant-context evidence are related but can fail independently.

6. **Make `32-05` static checks less formatting-sensitive.**
   - Prefer imported constants and behavioral tests where possible.
   - Keep regex checks for scope creep strings only.

---

# Final Risk Assessment

**Overall risk: MEDIUM.**

The plan set is directionally strong and likely to satisfy Phase 32 if executed with discipline. It correctly avoids graph renames, protects Phase 33 scope, and keeps model output candidate-only. The biggest delivery risks are `32-04` breadth, ambiguous merchant-context evidence rules, and incomplete first-class handling of `slot_resolution_gate` in the vocabulary layer. Addressing those before execution should reduce the risk to LOW-MEDIUM.

---

## Consensus Summary

Only the `--claude` reviewer was requested for this autopilot stage, so this section summarizes the single external review rather than multi-reviewer consensus.

### Agreed Strengths

- The five-plan split is directionally sound and keeps runtime graph names stable while adding target projections.
- Phase 33 `rag_context_build` / `claim_verify` behavior is explicitly kept non-runnable and out of scope.
- Owner/admin-only AgentRun, trace, and replay visibility is preserved as a hard security boundary.

### Agreed Concerns

- `slot_resolution_gate` should be represented from the vocabulary helper, not only as later trace metadata.
- `32-04` is broad and needs sharper merchant-context evidence source allowlists.
- Registry-consumption and authorization/static guards should rely on behavior tests where possible, not only grep-style checks.

### Divergent Views

- None captured; only Claude was run by request.

---

## Claude Re-Review After Codex Repairs

Reviewed at: 2026-06-28T13:25:48Z

## PASS

未发现剩余可执行 plan blocker/warning。已确认 accepted findings 在 repaired plans 中落地：

- `slot_resolution_gate` 已作为 first-class vocabulary/identity/projection 覆盖，并纳入 doc/source 一致性静态检查：`.planning/phases/32-intent-graph-migration/32-05-PLAN.md:171`
- registry 消费不再只靠静态 grep，32-02 要求 fake/monkeypatch 行为测试、异常/invalid route fail-closed 测试和 secondary static guard。
- slot freshness/idempotence 已收紧：确定性 current-time 输入、`SlotInheritanceDecision`、重复 resolution 不复活 rejected slots：`.planning/phases/32-intent-graph-migration/32-03-PLAN.md:155`
- merchant-context `resolved` 只允许 service-approved `BusinessFactRefV1` 来源，并禁止从 LLM/memory/slots/raw IDs 推导：`.planning/phases/32-intent-graph-migration/32-04-PLAN.md:249`
- `target_merchant_context.status == "resolved"` 非授权输入的测试要求已写入：`.planning/phases/32-intent-graph-migration/32-04-PLAN.md:264`
- final static checks 避免纯格式脆弱断言：要求 import/inspect `ADMIN_RUN_VISIBILITY_ROLES == {"admin"}`、只扫描 command-bearing validation lines、并校验 mapping doc 与 helper 一致：`.planning/phases/32-intent-graph-migration/32-05-PLAN.md:173`
- Phase 33 scope 保持 deferred/non-runnable，MOCA-approved pytest 命令规则已纳入最终 gate：`.planning/phases/32-intent-graph-migration/32-05-PLAN.md:170`

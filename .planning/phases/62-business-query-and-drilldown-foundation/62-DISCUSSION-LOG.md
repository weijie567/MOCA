# Phase 62: Business Query And Drilldown Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `62-CONTEXT.md`; this log preserves alternatives considered.

**Date:** 2026-07-09T18:48:27+08:00
**Phase:** 62-business-query-and-drilldown-foundation
**Areas discussed:** Query contract and phase depth; Runtime scope and no-existence-leak; Answer context and drilldown; Projection UI and eval; Deferrals and phase boundaries

---

## Query Contract And Phase Depth

| Question | Option | Description | Selected |
|---|---|---|---|
| Phase 62 should deliver to what depth? | Complete foundation | Contract, policy, runtime skeleton, answer context, projection/UI/eval, and aggregate/list/detail/breakdown/compare all enter Phase 62. | yes |
| Phase 62 should deliver to what depth? | Aggregate plus list/detail only | `breakdown` and `compare` would remain schema stubs. | |
| Phase 62 should deliver to what depth? | Metric/drilldown MVP only | Other business-query types would be deferred. | |
| Relationship between business_query and existing business_metric_query? | business_query primary | `business_query` becomes the long-term contract; `business_metric_query` maps into it as compatibility. | yes |
| Relationship between business_query and existing business_metric_query? | Keep extending business_metric_query | Rename later. | |
| Relationship between business_query and existing business_metric_query? | Long-term parallel contracts | Keep both indefinitely. | |
| Should operation taxonomy be locked now? | Lock now | `aggregate/list/detail/breakdown/compare` are read operations; `draft/execute` stay in action path. | yes |
| Should operation taxonomy be locked now? | Lock aggregate/list/detail only | Defer `breakdown/compare` operation decisions. | |
| Should operation taxonomy be locked now? | No operation taxonomy | Express via resource/metric fields only. | |
| Initial resource coverage? | order/refund_case/ticket/coupon_record/merchant_metric | Covers Phase 61 metric sources and after-sales drilldown needs. | yes |
| Initial resource coverage? | order/refund_case/ticket only | Defer coupon and merchant metric. | |
| Initial resource coverage? | order only | Validate list/detail pattern narrowly. | |

**User's choice:** `AAAA`

---

## Runtime Scope And No-Existence-Leak

| Question | Option | Description | Selected |
|---|---|---|---|
| Separate authorized merchant scope and target merchant? | Separate them | Business query uses authorized scope; actions remain bound to one target merchant. | yes |
| Separate authorized merchant scope and target merchant? | Document only | Keep current run_scope behavior. | |
| Separate authorized merchant scope and target merchant? | Keep single target merchant | Do not introduce authorized scope model for query. | |
| Where should backend read execution live? | BusinessFactService owns compiler/executor | Repositories expose controlled methods only; no generic list exposure. | yes |
| Where should backend read execution live? | Tool runtime owns compiler | BusinessFactService only checks permission. | |
| Where should backend read execution live? | Repository generic list/filter | Upper layers pass filters. | |
| What no-existence-leak semantics apply? | Permission before existence | Out-of-scope merchant/resource/id returns safe scope-denied or empty-safe result. | yes |
| What no-existence-leak semantics apply? | Detail only | List uses ordinary empty result. | |
| What no-existence-leak semantics apply? | Merchant filter only | Resource ids are not specially handled. | |
| Where enforce `current_snapshot` compatibility? | Descriptor plus service boundary | Graph can clarify early; service is final gate. | yes |
| Where enforce `current_snapshot` compatibility? | Graph/slot gate only | Service trusts upstream. | |
| Where enforce `current_snapshot` compatibility? | Tool schema enum only | No per-metric compatibility rule. | |

**User's choice:** `1 a 2 a 3 a 4 a`

---

## Answer Context And Drilldown

| Question | Option | Description | Selected |
|---|---|---|---|
| Should query/answer/cursor all enter Phase 62? | All three | `last_query_spec`, `last_answer_context`, and `result_cursor` are required. | yes |
| Should query/answer/cursor all enter Phase 62? | Only last_query_spec | Defer answer context and cursor. | |
| Should query/answer/cursor all enter Phase 62? | No new structure | Extend active slots only. | |
| What should answer context store? | Replayable spec plus safe metadata | Result ids/refs, allowed drilldowns, shown fields, cursor, scope/time/filter summary; no raw rows. | yes |
| What should answer context store? | Full rows | Store complete list result for follow-up use. | |
| What should answer context store? | Natural language summary | Store text only. | |
| How should drilldown follow-ups execute? | Re-execute backend query | Derive new operation from `last_query_spec` and revalidate. | yes |
| How should drilldown follow-ups execute? | Read prior answer context | Reuse previous data. | |
| How should drilldown follow-ups execute? | LLM inference | Let LLM infer from prior answer. | |
| Should missing-slot/follow-up handling generalize? | expected-slot-type flow | Time, resource id, merchant filter, and field/drilldown answers share one mechanism. | yes |
| Should missing-slot/follow-up handling generalize? | Metric time only | Other slots remain later work. | |
| Should missing-slot/follow-up handling generalize? | Per-slot branches | Keep if/else handling. | |

**User's choice:** `1 a 2 a 3 a 4 a`

---

## Projection UI And Eval

| Question | Option | Description | Selected |
|---|---|---|---|
| Must frontend support list/detail result types? | Typed payload and basic display | Timeline/Details distinguish aggregate/list/detail/breakdown/compare/RAG/clarification/unsupported. | yes |
| Must frontend support list/detail result types? | Backend text first | Frontend work later. | |
| Must frontend support list/detail result types? | Aggregate only | No structured list/detail display. | |
| What safe projection granularity? | Per-resource allowlist | Displayable fields, PII/redaction, prompt payload, and UI payload per resource. | yes |
| What safe projection granularity? | Global safe scalar filter | One global filter. | |
| What safe projection granularity? | final_response selects fields | No projection owner. | |
| What eval/golden coverage is required? | Drilldown plus permission/no-leak | Include multi-turn drilldown, permissions, list/detail no-existence-leak. | yes |
| What eval/golden coverage is required? | Happy path only | Minimal drilldown tests. | |
| What eval/golden coverage is required? | Backend unit only | No golden/e2e requirement. | |
| How deep should breakdown/compare go? | Contract plus one runtime/eval example | Avoid schema-only promises. | yes |
| How deep should breakdown/compare go? | Schema/docs only | No runtime. | |
| How deep should breakdown/compare go? | Fully defer | No Phase 62 coverage. | |

**User's choice:** `1 a 2 a 3 a 4 a`

---

## Deferrals And Phase Boundaries

| Question | Option | Description | Selected |
|---|---|---|---|
| Should Phase 62 handle risk/action taxonomy? | Defer to Phase 63 | Phase 62 only prevents read query from mixing into action path. | yes |
| Should Phase 62 handle risk/action taxonomy? | Minimal enum adjustment | Small local cleanup. | |
| Should Phase 62 handle risk/action taxonomy? | Handle in Phase 62 | Expand Phase 62 scope. | |
| Should Phase 62 handle RAG risk label drift? | Defer to Phase 64 | Preserve business/RAG boundary only. | yes |
| Should Phase 62 handle RAG risk label drift? | Fix manual_review_sensitive only | Local hotfix. | |
| Should Phase 62 handle RAG risk label drift? | Full registry now | Expand Phase 62 scope. | |
| Should Phase 62 handle global trace/event/frontend label registry? | Business-query payload only | Global registry belongs to Phase 65. | yes |
| Should Phase 62 handle global trace/event/frontend label registry? | Global registry now | Expand Phase 62 scope. | |
| Should Phase 62 handle global trace/event/frontend label registry? | Do not touch frontend/event payload | Would miss Phase 62 UI contract. | |
| Should Phase 62 add Phase 67 now? | Record recommendation only | No ROADMAP mutation during discuss; revisit after Phase 62 plan acceptance. | yes |
| Should Phase 62 add Phase 67 now? | Register immediately | Mutate roadmap now. | |
| Should Phase 62 add Phase 67 now? | Do not mention | Lose the hardcoding review conclusion. | |

**User's choice:** `1 a 2 a 3 a 4 a`

---

## the agent's Discretion

- Exact class/module names for query registry, descriptors, and specs.
- Exact frontend layout, as long as typed result kinds and no raw payload exposure are preserved.
- Exact eval fixture format and focused test split.

## Deferred Ideas

- Phase 63: risk/action taxonomy and risk severity/disposition.
- Phase 64: RAG risk label registry.
- Phase 65: global event/label/response-kind registry and frontend/backend parity.
- Phase 66: demo/config/test hygiene.
- Future Phase 67: state machine registry and DB/API/frontend status constraint hardening.

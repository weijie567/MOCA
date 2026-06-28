---
phase: 32
review_source: 32-REVIEWS.md
reviewer: claude
adjudicated_at: "2026-06-28T13:11:00Z"
status: repaired
---

# Phase 32 Plan Review Decisions

## Decision Summary

Claude's review was directionally correct. The accepted issues are plan-quality gaps, not code defects, because Phase 32 execution has not started.

Accepted repairs are limited to the Phase 32 planning artifacts. They tighten vocabulary coverage, behavioral tests, deterministic slot policy, merchant-context evidence allowlists, and static contract checks before execution.

## Accepted

1. `slot_resolution_gate` is not first-class enough in `32-01`.
   Evidence: `32-01-PLAN.md` claims APF-11 coverage for `slot_resolution_gate`, but Task 1's concrete alias list omits it. Repair: add explicit vocabulary entries/tests for `extract_slots` / `slot_resolution_gate`.

2. Synthetic `safety_pre_route` projection needs clearer semantics.
   Evidence: `32-01` maps `classify_intent:pre_route` but does not state where that semantic trace entry comes from. Repair: state it is projection metadata derived from classifier pre-route trace/metrics, not a registered graph node.

3. Unknown graph-name passthrough should not be labeled as a known runtime entry.
   Evidence: `32-01` says unknown names return status `runtime`, which can be misread as known/registered. Repair: add `unknown_passthrough`.

4. Projection helper tests should prove original trace fields are preserved.
   Evidence: `32-01` requires preserving `node`, but not arbitrary existing keys. Repair: add an explicit preservation test.

5. Registry-consumption proof in `32-02` should be behavioral.
   Evidence: Task 2 allowed monkeypatch tests or static checks. Static checks alone cannot prove consumers call the registry. Repair: require fake/monkeypatched registry tests and exact replacement in `routing.py` / `classify_intent.py`.

6. Intent policy fail-closed edge cases need explicit tests.
   Evidence: `32-02` does not call out unknown/malformed values or registry exceptions. Repair: add tests for unknown intent/operation, invalid registry output, and registry exception fallback.

7. Slot policy freshness and idempotence need sharper tests.
   Evidence: `32-03` covers stale/wrong-thread/incompatible slots, but not deterministic time injection or repeated resolution. Repair: require deterministic time context and idempotence/rejected-metadata tests.

8. `32-04` merchant-context `resolved` source rule is too broad.
   Evidence: Task 2 allows "`last_business_context_refs`, `business_context`, or equivalent graph state". Repair: replace with an explicit allowlist of service-approved `BusinessFactRefV1` sources and tests for no raw identifier leakage.

9. Target merchant context must be proven non-authoritative.
   Evidence: `32-04` says guards must not read it, but tests should prove a resolved status cannot widen access. Repair: add explicit non-authority tests.

10. `32-05` static checks should avoid brittle formatting-only assertions where behavior/import checks are possible.
    Evidence: exact source string checks for admin roles and broad validation-command scans may false-positive. Repair: import constants / test behavior where possible and scan only command-bearing lines.

11. `32-MVP-TARGET-MAPPING.md` should be checked against the vocabulary helper.
    Evidence: `32-05` says the doc mirrors the helper but does not require a source-to-doc consistency test. Repair: add a static consistency check.

## False Positives

1. `TraceResponse` schema ownership in `src/api/schemas/approvals.py`.
   Evidence: current `src/api/routers/traces.py` imports `TraceResponse` from `src.api.schemas.approvals`, so `32-04` following that local ownership is consistent. No plan change needed.

## Disagreed

1. Split `32-04` into new numbered plan files.
   Rationale: the risk is real, but `32-04` already has three ordered tasks that separate trace projection, merchant-context evidence, and visibility tests. A new numbered split would churn roadmap bookkeeping after the native GSD checker already passed the five-plan structure. Repair tightens task sequencing and acceptance criteria instead.

2. Move `SlotPolicyRegistry` out of `src/agent/intent_policy.py`.
   Rationale: current local code already houses `IntentPolicyRegistry` and `SlotPolicyRegistry` together. Phase 32 is a migration boundary phase, not a module extraction phase. The plan keeps slot APIs named as slot policy to avoid intent-policy semantic confusion.

3. Treat `business_fact_ref_count` as an information-disclosure defect for authorized surfaces.
   Rationale: `32-04` keeps owner/admin-only visibility and forbids unauthorized error-path exposure. A bounded count on authorized trace/run surfaces is acceptable if raw refs and identifiers are not exposed.

## Deferred

1. Physical `slot_resolution_gate` registered graph node.
   Target: post-Phase 32 graph-extraction work, after compatibility projection and registry-owned behavior are proven. Phase 32 keeps the semantic projection boundary only.

2. Same-merchant AgentRun visibility.
   Target: Phase 35/36+ ownership/access work named in existing plan guardrails. Phase 32 must not broaden run/trace/replay authorization.

# Phase 45: Memory Lifecycle Wiring for Case Working Context - Discussion Log

> Audit trail only. Do not use as input to planning, research, or execution agents.
> Decisions are captured in `45-CONTEXT.md`; this log preserves the alternatives considered.

**Date:** 2026-07-03
**Phase:** 45-memory-lifecycle-wiring-for-case-working-context
**Areas discussed:** GAD-01 precondition, lifecycle integration shape, active CWC read, thread-case link, terminal CWC write, content projection, ReAct decoupling

---

## GAD-01 Precondition

| Option | Description | Selected |
| --- | --- | --- |
| A / loop-local | Observation-to-slot feedback remains inside future `investigate` planner context and does not write graph-global `active_slots`. | Yes |
| B / discovered slot surface | `investigate` writes a new global discovered-slot state surface and updates contract/field registry. |  |

**User's choice:** A / loop-local.
**Notes:** The GAD-01 decision was checked in `.planning/DEFERRED-DECISIONS.md`, `.planning/AGENTIC-INVESTIGATION-DISCUSSION.md`, and `docs/target-agent-platform-architecture-plan.md`. It is acceptable: the old "must decide before implementation" wording has been replaced by "loop-local decided", and ReAct is decoupled from memory Phase 45.

---

## Lifecycle Integration Shape

| Option | Description | Selected |
| --- | --- | --- |
| Stable lifecycle adapter plus existing terminal finalizer | Put CWC read/link/write orchestration behind a stable adapter; first production write hook can reuse `src/api/services/agent_run_memory.py`. | Yes |
| Hide CWC writes in `final_response` | Add side effects to response generation. |  |
| Force graph edge rewrite first | Register `memory_write` in graph and make graph topology the lifecycle contract. |  |

**User's choice:** Stable lifecycle adapter plus existing terminal finalizer.
**Notes:** Code scout found `memory_write` is callable but not graph-registered; completed `/agent-runs` already invoke terminal memory write through `finalize_completed_agent_run_memory`. The adapter rule keeps Phase 45 safe for a later ReAct graph refactor.

---

## Active CWC Read

| Option | Description | Selected |
| --- | --- | --- |
| Post-slot memory-context seam | Resolve case identity after slots, load active CWC before `investigate` / recommendation via the current memory-context load seam. | Yes |
| Read inside `investigate` only | Let investigation pull CWC ad hoc. |  |
| Delay read until final response | Load CWC only for response wording. |  |

**User's choice:** Post-slot memory-context seam.
**Notes:** This matches spec `memory_context_load` semantics and keeps CWC as contextual input rather than tool authority or policy evidence.

---

## Thread-Case Link

| Option | Description | Selected |
| --- | --- | --- |
| Explicit run-auto link after case resolution | Call `ConversationRepository.link_case(..., link_source="run_auto")` when a trusted case id exists. | Yes |
| Auto-link from every message append | Make generic message persistence infer case membership. |  |
| Defer linking again | Keep Phase 44 callable surface without a production caller. |  |

**User's choice:** Explicit run-auto link after case resolution.
**Notes:** `append_message` must remain non-linking. Link creation belongs to a lifecycle adapter once a run has a trusted canonical `refund_cases.id`.

---

## Terminal CWC Write

| Option | Description | Selected |
| --- | --- | --- |
| Completed terminal runs only | Write CWC only for successful completed runs with final response and resolved case id; skip interrupted/error/missing-final-response paths. | Yes |
| All terminal states | Try to write CWC for clarification, approval pending, interrupted, cancelled, and errors. |  |
| Manual-only for now | Do not auto-write CWC in Phase 45. |  |

**User's choice:** Completed terminal runs only.
**Notes:** Clarification-only responses may link a resolved case but should skip CWC content write unless planning proves a safe deterministic update.

---

## Content Projection

| Option | Description | Selected |
| --- | --- | --- |
| Deterministic projection | Map final run state to `CaseWorkingContextContentV1` with refs/summaries only. | Yes |
| LLM summarizer | Use a model to summarize CWC updates. |  |
| Raw transcript snapshot | Store large raw conversation/tool payloads. |  |

**User's choice:** Deterministic projection.
**Notes:** No LLM summarizer in Phase 45. Claims and verified facts remain separate; tool facts store references/summaries with `observed_at`; policy body text and sensitive raw PII are not stored.

---

## Safety And Failure Semantics

| Option | Description | Selected |
| --- | --- | --- |
| Reuse Phase 44 service semantics | PII block emits blocked audit, version conflict skips, memory failures do not roll back completed user response. | Yes |
| Merge on conflict | Automatically merge conflicting CWC updates. |  |
| Overwrite latest | Last-write-wins CWC update. |  |

**User's choice:** Reuse Phase 44 service semantics.
**Notes:** Phase 45 is caller-side wiring. It must not weaken the repository/service behavior that Phase 44 already verified.

---

## the agent's Discretion

- Exact lifecycle adapter class/function names.
- Exact additive `AgentState` CWC field names.
- Whether implementation extends `memory_write` directly or adds a CWC-specific helper under the terminal finalizer.
- Exact plan split, as long as plan granularity follows the MOCA phase-level planning rule.

## Deferred Ideas

- Future investigate ReAct implementation.
- GAD-01 option B discovered slot surface.
- Case precedent generation from closed cases.
- Long-term explicit-preference write path.
- Session memory repositioning after CWC.
- Broad graph topology/vocabulary reconciliation beyond what Phase 45 minimally needs.

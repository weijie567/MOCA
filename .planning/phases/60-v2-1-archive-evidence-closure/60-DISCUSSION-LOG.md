# Phase 60: v2.1 Archive Evidence Closure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `60-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-07-08T10:55:24Z
**Phase:** 60-v2-1-archive-evidence-closure
**Mode:** autopilot auto-discuss
**Areas discussed:** Evidence closure scope, planning granularity, evidence standards

---

## Evidence Closure Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Close only missing `*-VERIFICATION.md` files | Narrowest interpretation of Phase 60, but leaves Nyquist and archive audit gaps open. | |
| Close formal verification, Nyquist validation, metadata, and milestone audit gaps | Matches ROADMAP success criteria and `.planning/v2.1-MILESTONE-AUDIT.md`. | yes |
| Reopen runtime implementation across old phases | Too broad; Phase 60 is not a runtime behavior phase unless evidence proves a real defect. | |

**Autopilot choice:** Close formal verification, Nyquist validation, metadata, and milestone audit gaps.
**Notes:** Phase 59 already closed the runtime approval-resume terminal memory finalization gap. Phase 60 should not reimplement old phase behavior.

---

## Planning Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| One large plan for all evidence closure | Fast to write, but too broad for reliable review and execution. | |
| Split by dependency-ordered evidence type | Formal verification first, validation/Nyquist second, final audit/state reconciliation last. | yes |
| Split into one plan per old phase | Very precise but likely excessive for an evidence-only phase. | |

**Autopilot choice:** Split by dependency-ordered evidence type.
**Notes:** Plan-level granularity must satisfy MOCA's hard constraint against one oversized plan covering multiple domains and gates.

---

## Evidence Standards

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing summaries without new checks | Too weak for strict archive evidence. | |
| Source/test-backed verification artifacts with approved commands | Matches GSD archive expectations and MOCA test-entrypoint rules. | yes |
| Run broad full-suite tests for every target phase | Strong but likely wasteful; use focused commands unless a broad gate is justified. | |

**Autopilot choice:** Source/test-backed verification artifacts with approved commands.
**Notes:** Commands must use `UV_CACHE_DIR=/tmp/uv-cache uv run ...` or `.venv/bin/...`; bare `pytest` and bare `python -m pytest` are invalid in MOCA.

## the agent's Discretion

- Choose exact plan grouping as long as formal verification, validation/Nyquist, and final archive audit remain separate enough to review.
- Choose focused test commands per target phase from existing phase summaries and code evidence.
- Decide when a validation artifact is a document/spec validation artifact rather than runtime pytest, especially for Phase 50's SPEC-only scope.

## Deferred Ideas

None.

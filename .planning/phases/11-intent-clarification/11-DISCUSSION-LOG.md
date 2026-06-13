# Phase 11: Intent / Clarification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 11-intent-clarification
**Areas discussed:** reference adoption/exclusion, planning split, ordinary clarification vs approval boundary, safety constraints

---

## Reference Adoption / Exclusion

| Option | Description | Selected |
| --- | --- | --- |
| Adopt triage structure only | Use reference repos for classify-then-route and structured-output routing patterns, while adapting to MOCA contracts. | yes |
| Copy reference domain prompts/workflows | Reuse email/customer-support prompt content or notebook workflow directly. | no |
| Use free tool loop as Phase 11 core | Let LLM loop freely through tools as part of intent/clarification. | no |

**User's choice:** Adopt `agents-from-scratch-ts` triage routing and LangGraph adaptive RAG structured router patterns; exclude customer-support notebook, email prompts, free tool loop, and memory-driven triage preferences.

**Notes:** These are planning constraints, not implementation code.

---

## Ordinary Clarification / Approval Boundary

| Option | Description | Selected |
| --- | --- | --- |
| Separate contracts | Ordinary chat clarification and approval respond/decision remain separate paths. | yes |
| Unified clarification path | Treat approval `respond` / `needs_info` as the same as ordinary clarification. | no |
| Allow ordinary chat approval decisions | Let chat text create `approval_result` or trusted resume. | no |

**User's choice:** Keep ordinary chat clarification separate from approval respond/decision lifecycle.

**Notes:** Ordinary chat cannot create `approval_result`, resume commands, or trusted approval decisions.

---

## Plan Split

| Option | Description | Selected |
| --- | --- | --- |
| Five small plans | Split Phase 11 into schema, pre-router, slot routing, clarification gate, and manifest/golden tests. | yes |
| One large plan | Implement Phase 11 as one broad plan. | no |
| Start coding directly | Skip context/planning and implement immediately. | no |

**User's choice:** Split into five plans: `11-01` through `11-05`.

**Notes:** The user explicitly requested discuss before planning and requested targeted review after planning.

---

## Deferred Ideas

- Trusted approval lifecycle and approval `respond` resume remain Phase 13.
- Real session-memory CAS and safe slot continuity remain Phase 12.
- Free write/action tool loops remain out of scope.

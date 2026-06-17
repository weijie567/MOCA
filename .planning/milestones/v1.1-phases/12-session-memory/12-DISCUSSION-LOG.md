# Phase 12: Session Memory - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `12-CONTEXT.md` - this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 12-session-memory
**Areas discussed:** Persistence Boundary and Schema, Read and Write Timing, CAS and Conflict Semantics, Safe Slot Inheritance, Observability and Evidence Boundary
**Interaction note:** Codex `request_user_input` was unavailable in Default mode, so the workflow fallback selected the recommended discussion set and conservative defaults grounded in the roadmap, contract spec, prior phase context, and current code.

---

## Persistence Boundary and Schema

| Option | Description | Selected |
| --- | --- | --- |
| PostgreSQL authoritative `session_memories` | Matches `docs/contract-spec.md` and Phase 12 decomposition; supports version CAS and tenant/user/thread isolation. | yes |
| LangGraph checkpointer only | Lower effort, but spec explicitly says the checkpointer is not authoritative session memory after Phase 12. | |
| Redis authoritative memory | Faster cache shape, but explicitly forbidden for authoritative Phase 12 memory. | |

**Selected default:** PostgreSQL authoritative `session_memories`.
**Notes:** Preserve Redis only as optional non-authoritative short-TTL helper if planning needs it; correctness remains Postgres CAS.

---

## Read and Write Timing

| Option | Description | Selected |
| --- | --- | --- |
| Read before slot extraction; write after safe resolution | Reuses existing `session_memory_load` placement and avoids writing unvalidated classifier output. | yes |
| Write during intent classification | Earlier persistence but unsafe because candidate slots are only hints and Phase 11 forbids whole-object trust. | |
| Write only manually/offline | Avoids runtime complexity but fails same-thread continuity goal. | |

**Selected default:** Read before slot extraction; write after safe resolution.
**Notes:** Planner may choose dedicated `memory_write` node or finalizer hook, but writes must not bypass validation/CAS/fallback rules.

---

## CAS and Conflict Semantics

| Option | Description | Selected |
| --- | --- | --- |
| Version CAS plus deterministic merge | Satisfies SESSION-01 and prevents silent lost updates under concurrent same-thread runs. | yes |
| Last-write-wins | Simpler but explicitly forbidden by spec and unsafe for slot continuity. | |
| Always fail on first conflict | Safe but poorer continuity; acceptable only when deterministic merge cannot preserve safety. | |

**Selected default:** Version CAS plus deterministic merge.
**Notes:** Conflict fallback is allowed only when deterministic merge cannot preserve safety.

---

## Safe Slot Inheritance

| Option | Description | Selected |
| --- | --- | --- |
| Strict inheritance with scope, freshness, intent compatibility, and explicit override | Matches existing `route_after_slots` trust checks and prevents unsafe action/risk/evidence shortcuts. | yes |
| Same-thread value reuse without per-slot metadata | Easier UI continuity but too weak for action/risk workflows. | |
| Never inherit slots | Safest but defeats Phase 12 same-thread continuity. | |

**Selected default:** Strict inheritance with scope, freshness, intent compatibility, and explicit override.
**Notes:** Inherited slots can help slot completeness only; they cannot satisfy evidence, risk, approval, or action authorization.

---

## Observability and Evidence Boundary

| Option | Description | Selected |
| --- | --- | --- |
| Disable/read-switch fallback with telemetry and memory-is-not-evidence tests | Matches SESSION-03 and keeps rollback behavior identical to the Phase 10 empty adapter. | yes |
| Hard fail when memory is unavailable | Makes memory a correctness dependency and hurts ordinary current-turn flows. | |
| Treat memory summaries as evidence | Explicitly forbidden because KnowledgeService is the only policy evidence producer. | |

**Selected default:** Disable/read-switch fallback with telemetry and memory-is-not-evidence tests.
**Notes:** Disabled/unavailable memory should continue with `continuity_claimed=False` and clarify only if required slots remain missing.

---

## the agent's Discretion

- Exact module names under `src/memory/`.
- Exact graph placement for safe session writes, provided the context rules are preserved.
- Slot TTL defaults, summary length limits, and fixture organization.

## Deferred Ideas

- Long-term/case memory, memory identity, tombstones, embeddings, async extraction, and review workflow.
- Trusted approval `needs_info` resume and approval/action snapshot work.
- Full ReplayEventV3 read API and retention/redaction work.

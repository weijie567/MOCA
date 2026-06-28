# Phase 33: RAG Context Build and Claim Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `33-CONTEXT.md`; this log preserves the alternatives considered.

**Date:** 2026-06-29
**Phase:** 33-rag-context-build-and-claim-verification
**Areas discussed:** architecture target, graph split, verified evidence package, claim verification, plan granularity

---

## Interaction Notes

The Codex interactive question tool was unavailable in Default mode. Per `$gsd-discuss-phase` fallback behavior, Codex selected the recommended discussion scope after reading project context and current code.

The user then clarified:

> `/Users/ming/projects/MOCA/docs/target-agent-platform-architecture-plan.md 这是之前的架构迁移目标`

Codex read that file and treated it as the architecture migration target for Phase 33, while preserving `docs/contract-spec.md` as the normative contract source.

---

## Gray Area Selection

| Option | Description | Selected |
| --- | --- | --- |
| All four (Recommended) | Discuss Phase 22 kernel migration shape, real graph node split, claim verification strictness, and verification/plan slicing. | yes |
| Core only | Discuss only graph node split and claim verification routing; let Codex lock the rest from codebase defaults. | no |
| Custom subset | Present a numbered list and let the user pick a subset. | no |

**Captured decision:** Discuss all major Phase 33 gray areas because APF-13/APF-14 spans service boundary, graph routing, schemas, action-gating safety, and eval gates.

---

## Architecture Target

| Option | Description | Selected |
| --- | --- | --- |
| Architecture-plan led | Use `target-agent-platform-architecture-plan.md` as migration target and `contract-spec.md` as normative conflict resolver. | yes |
| Contract-spec only | Ignore architecture-plan detail unless repeated in `contract-spec.md`. | no |
| Current-code led | Preserve the Phase 22 code shape and only rename fields/nodes. | no |

**Captured decision:** Phase 33 must read and follow the target architecture plan. Current Phase 22 code is implementation raw material, not the final platform boundary.

---

## RAG Graph Split

| Option | Description | Selected |
| --- | --- | --- |
| Three-stage split | `KnowledgeService.search` inside `investigate`; `rag_context_build` deterministic node; `claim_verify` post-generation node. | yes |
| Keep inside generation | Continue building/verifying RAG context inside `generate_recommendation` with target aliases only. | no |
| Single RAG node | Create one RAG node that does retrieval, package build, generation, and verification. | no |

**Captured decision:** Use the three-stage split from the architecture target. `rag_context_build` and `claim_verify` should become real graph semantics in Phase 33.

---

## Service Boundary

| Option | Description | Selected |
| --- | --- | --- |
| KnowledgeService boundary | Route verified-context build and claim verification through `KnowledgeService` public methods. | yes |
| Agent-only RAG package | Keep all RAG/claim logic under `src/agent/rag_context` with direct node orchestration. | no |
| New external service | Simulate a separately deployed knowledge service. | no |

**Captured decision:** Converge to `KnowledgeService.search`, `KnowledgeService.build_verified_context`, and `KnowledgeService.verify_claims` as the platform boundary, without physical microservice extraction.

---

## Verified Evidence Package

| Option | Description | Selected |
| --- | --- | --- |
| Stable package schema | Add/adapt `VerifiedEvidencePackageV1` with package status, items, maps, projections, rejected/stale/conflict refs, versions, and snapshot refs. | yes |
| Reuse RagContextBundle as-is | Treat current `RagContextBundle` as the complete target package. | no |
| Prompt string only | Build a bounded prompt string and rely on citation validation. | no |

**Captured decision:** `RagContextBundle` can be reused internally, but Phase 33 needs a stable package contract aligned with architecture/spec.

---

## Claim Verification Strictness

| Option | Description | Selected |
| --- | --- | --- |
| Rules-first hard gates | Use identity/scope/hash/effective-date/business-fact gates plus domain rule checks; semantic review only assists selected cases. | yes |
| Semantic-first verifier | Ask an LLM-style verifier to decide support and route around hard gates. | no |
| Citation membership only | Treat cited evidence membership as enough support for claims. | no |

**Captured decision:** Claim verification must be rules-first. Unsupported user-visible claims and unsupported action claims are blocked; business fact claims require `BusinessFactRefV1`.

---

## Plan Granularity

| Option | Description | Selected |
| --- | --- | --- |
| Split into focused plans | Break Phase 33 into contracts/service boundary, `rag_context_build`, `claim_verify`, integration gates, and final verification. | yes |
| One broad plan | Follow roadmap placeholder `33-01-PLAN.md` as one all-encompassing implementation plan. | no |
| Defer split to execution | Let executor split after a large plan is written. | no |

**Captured decision:** A single broad Phase 33 plan would violate MOCA project planning rules for service-boundary/platform-foundation phases. Planning must split before execution.

---

## the agent's Discretion

- Exact class/file names and enum spelling can be chosen during planning if contract semantics and tests are stable.
- Exact compatibility shims between `RagContextBundle`, `VerifiedEvidencePackageV1`, existing verifier result schemas, and target package/bundle names are planner discretion.
- Exact manual-review representation can follow current graph capabilities if no dedicated manual-review node exists.

## Deferred Ideas

- Full retrieval algorithm expansion, external search backend, and retrieval tuning.
- Phase 34 approval/action draft binding.
- Phase 35 broad replay/eval hardening.
- Real external execution.


---
phase: 09-business-tool-facade
purpose: "Durable authoritative re-verification contract for Phase 8/9 ownership boundary"
created: 2026-06-13
authoritative_sources:
  - ".planning/ROADMAP.md"
  - ".planning/phases/09-business-tool-facade/09-CONTEXT.md"
  - ".planning/phases/09-business-tool-facade/09-RESEARCH.md"
---

# Phase 8/9 Ownership Boundary — Re-Verification Contract

## Authoritative Phase 9 Goal

> **Route read business tools through BusinessToolService using trusted ToolCallContext and typed ToolResultV2.**
>
> -- `.planning/ROADMAP.md`, Phase 9: Business Tool Facade

The Phase 9 goal scopes to **read business tools**. It does not claim ownership of policy knowledge retrieval.

## Locked Ownership Decision

From `.planning/phases/09-business-tool-facade/09-CONTEXT.md` (locked, seeded 2026-06-06):

> **Do NOT own policy knowledge:** `search_policy_adapter` and policy EvidenceRef extraction
> (`_evidence_refs_from_data` for policy chunks) belong to the Phase 8 KnowledgeService, not the
> BusinessToolService. Phase 9 does not re-own Knowledge/RAG retrieval or policy evidence production
> and emits business-fact provenance through `business_fact_refs` only.

## Phase 8 Owner

**PolicyKnowledgeService** (`src/knowledge/service.py`) is the live owner of policy retrieval execution. The `retrieve_policy_evidence` node (`src/agent/nodes/retrieve_policy_evidence.py`) constructs a `PolicyKnowledgeService` instance and awaits `service.search(request, context)` directly. This is the correct and intentional architecture.

## Executable Contract

| Concern | Owner | Executable Path | Boundary |
|---------|-------|-----------------|----------|
| Business reads (order/refund/ticket) | Phase 9 `BusinessToolService` | `load_business_context` -> `BusinessToolService.fetch_context` -> `ToolRegistry.invoke` -> adapters | Business reads execute through the facade |
| Policy retrieval (search_policy/sop/case_memory) | Phase 8 `PolicyKnowledgeService` | `retrieve_policy_evidence` -> `PolicyKnowledgeService.search` -> `LegacyRagKnowledgeAdapter` | Policy retrieval executes through Phase 8 service |
| Retrieval descriptors in Phase 9 registry | Phase 9 `ToolRegistry` | Declared with `adapter=None`; invoke returns `status="unavailable"` | Declaration/validation catalog only; NOT a transfer of execution ownership |
| Write/action execution | Outside facade | Separate node/tool path | Never executes through `BusinessToolService.invoke_tool` |

## Disposition of Verifier's Expanded Claim

The original `09-VERIFICATION.md` (read-only record of the initial verification gaps) asserts:

> "All business and retrieval tools run through one registry/service contract."
> -- Truth #2, status: FAILED

**Disposition: This is a scope conflict, not an implementation requirement.**

The verifier's expanded claim interprets the Phase 9 goal as requiring ALL tools (including retrieval) to execute through a single registry/service. The authoritative Phase 9 goal from ROADMAP says "Route **read** business tools through BusinessToolService." The locked CONTEXT decision explicitly states "Do NOT own policy knowledge." The retrieval descriptors in the Phase 9 registry are declaration/validation catalog entries — they provide a unified declaration surface for the Phase 10 `investigate` bounded-loop, but their `adapter=None` contract means they do not transfer execution ownership from `PolicyKnowledgeService` to `BusinessToolService`.

This is an **invalid scope expansion** by the verifier, not an implementation gap. The boundary artifact and executable tests below provide the authoritative inputs for the independent post-execution verifier to re-evaluate.

## Real Authorization Defects (Closed by Plans 09-06 and 09-07)

Two real authorization defects were identified during verification and are closed by the gap-closure plans:

1. **JWT scope widening (CR-01):** Verified token scopes were discarded after endpoint validation; `_trusted_tool_config` reconstructed permissions from the full role allowlist. **Closed by Plan 09-06** — token scopes are preserved and tool permissions are derived from the intersection of verified token scopes and role scopes.

2. **Merchant scope dropping (WR-01):** The router injected `merchant_scope` as a structured dict, but `retrieve_policy_evidence` accepted only `list` and converted non-list values to `None`. **Closed by Plan 09-07** — the policy node extracts `merchant_ids` from the structured scope.

## Executable Verifier Inputs

### Ownership Regression Test

**File:** `tests/agent/test_policy_retrieval_ownership.py`

This test module encodes the Phase 8/9 ownership boundary as executable assertions:

- `TestPolicyRetrievalOwnership` — proves `retrieve_policy_evidence` calls `PolicyKnowledgeService.search` (not `BusinessToolService`)
- `TestRetrievalDescriptorsDeclarationOnly` — proves retrieval descriptors exist in the registry with `adapter=None` and return `status="unavailable"` when invoked
- `TestBusinessReadDescriptorsExecutable` — proves business-read descriptors retain adapters (positive ownership boundary)
- `TestWriteDescriptorBlocked` — proves write tools are hard-blocked before adapter execution
- `TestOwnershipContractEncoding` — meta-assertion that the ownership tests never assert policy execution through `BusinessToolService`

### Full Phase 9 Regression Command

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/business_tools/ \
  tests/agent/test_nodes/test_load_business_context.py \
  tests/agent/test_nodes/test_retrieve_policy_evidence.py \
  tests/agent/test_policy_retrieval_ownership.py \
  tests/agent/test_graph.py \
  tests/test_agent_runs_api.py \
  tests/integration/test_auth.py \
  -q --tb=short
```

### Plan 09-06 Regression (JWT scope intersection)

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/integration/test_auth.py \
  tests/test_agent_runs_api.py \
  -q --tb=short
```

### Plan 09-07 Regression (merchant scope projection)

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/agent/test_nodes/test_retrieve_policy_evidence.py \
  tests/agent/test_graph.py \
  -q --tb=short
```

## Use by Independent Verifier

The independent post-execution `gsd-verifier` should use this boundary artifact together with:

1. `tests/agent/test_policy_retrieval_ownership.py` — executable ownership regression
2. Plan 09-06 executable regressions — JWT scope intersection evidence
3. Plan 09-07 executable regressions — merchant scope projection evidence

...to evaluate:
- The corrected ownership scope (retrieval descriptors are declaration-only, not a scope expansion requirement)
- The two real authorization defects (closed by 09-06 and 09-07)

**Do not treat the verifier's expanded Truth #2 ("all business and retrieval tools run through one registry/service contract") as a normative requirement.** The authoritative ROADMAP goal is narrower: "Route read business tools through BusinessToolService."

## What This Boundary Does NOT Do

- This artifact does NOT edit or recompute status, score, or requirements disposition in `09-VERIFICATION.md`, `ROADMAP.md`, or `REQUIREMENTS.md`.
- This artifact does NOT self-certify verification outcomes. Final verification status, score, and requirements disposition are owned by the independent post-execution `gsd-verifier`.
- This artifact does NOT edit `09-CONTEXT.md`, `09-REVIEW.md`, or any unrelated docs.

---

*Created: 2026-06-13*
*Phase: 09-business-tool-facade*
*Purpose: Durable re-verification input for independent verifier*

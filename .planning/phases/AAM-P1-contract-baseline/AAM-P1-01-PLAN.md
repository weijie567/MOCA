---
phase: AAM-P1
plan: AAM-P1-01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTRACT-BASELINE.md
autonomous: true
requirements:
  - AAM-P1-baseline-artifacts
  - AAM-readiness-status-vocabulary
  - AAM-follow-up-register-disposition
---

# AAM-P1-01 PLAN: Contract Baseline Artifacts

<objective>
Create the AAM-P1 contract baseline artifact for the Agent Architecture Migration workstream. This plan is docs-only and must not change MOCA source code, tests, schemas, migrations, API contracts, or runtime behavior.

The plan must produce `.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTRACT-BASELINE.md` with:

1. Contract inventory.
2. Current-vs-target evidence checklist.
3. Initial coverage matrix.
4. Spec consistency findings / planning deviations.
5. Identifier semantics.
6. Boris/GSD phase notes.
7. Phase planning follow-up register disposition.
8. Review checklist.
9. Readiness verdict.

AAM-P1 is not historical MOCA Phase 1. All headings, artifact names, and suggested commit messages must use `AAM-P1`.
</objective>

<traceability>
## Spec sections covered

- `docs/agent-architecture-spec.md` Section 19: AAM migration route, AAM-P1 outputs, phase planning traceability requirements, coverage matrix, follow-up register, and readiness verdict.
- `docs/agent-architecture-spec.md` Section 10: AgentState target schema, lifecycle matrix, canonical field registry, identifier semantics, and reset/merge rules.
- `docs/agent-architecture-spec.md` Sections 7-18: target graph/service boundaries, router contracts, Knowledge/RAG, Business Tools, Memory, Approvals/SLA/Risk, Actions, Observability/Replay, migration rollout, and cross-table enforcement matrix.
- `docs/agent-architecture-spec.md` Section 20: contract test and eval matrix requirements.
- `docs/agent-architecture-phase-decomposition.md` Sections 1, 2, 5, 6, and 7: readiness rules, AAM phase sequence, global coverage matrix, follow-up register, and next planning order.

## Spec consistency findings

- AAM-P1 must audit Section 19 instead of proving it correct by default.
- The baseline artifact must include `## Spec Consistency Findings` or `## Planning Deviations`.
- If Section 19 conflicts with phase decomposition, current source evidence, or AAM-P1 artifacts, record original requirement, conflicting evidence, recommended handling, readiness impact, owner, and status.
- If no inconsistency is found, write `None found after checking docs/agent-architecture-spec.md, docs/agent-architecture-phase-decomposition.md, current source evidence, and AAM-P1 artifacts`.
- Do not force unsupported, unreasonable, or inconsistent target contracts to `COVERED`; use `PARTIAL`, `MISSING`, or `DEFERRED_WITH_OWNER` according to evidence.

## Schema/migration owner

- AAM-P1 has no schema changes. `N/A with reason: docs-only baseline; no tables, columns, indexes, FKs, backfill reports, or read-switch are modified by AAM-P1`.
- AAM-P1 baseline artifact must assign schema/migration ownership to AAM-P2 through AAM-P11 where the spec names owner phases.
- Any future schema/service migration row must name read-switch owner, config/feature flag, fallback telemetry, rollback behavior, or `N/A with reason` in non-status fields only.

## Service/API owner

- AAM-P1 has no service/API changes. `N/A with reason: docs-only baseline; no service facade, API route, inbox entry, worker, or adapter changes`.
- AAM-P1 baseline artifact must identify service/API owner phases for KnowledgeService, BusinessToolService, MemoryService, ApprovalService, ActionExecutor, and Replay/RunLifecycle services.

## State/router impact

- AAM-P1 has no runtime state/router impact. `N/A with reason: docs-only baseline; no AgentState field, graph node, router, interrupt/resume, or final response behavior changes`.
- AAM-P1 baseline artifact must inventory current vs target AgentState fields, router decisions, graph path endpoints, and interrupt/resume semantics.

## Required tests

- AAM-P1 requires docs lint/manual review/checklist verification only because source code is unchanged.
- AAM-P1 execution artifact must define downstream contract, integration/golden, migration verification, and eval gates per owner phase.
- Every eval gate in the baseline must name blocking/non_blocking status, dataset owner/version/hash when known, or owner phase and acceptance gate when deferred.

## Acceptance criteria

- Acceptance criteria are the task-level criteria in this plan plus the final verification that `AAM-P1-CONTRACT-BASELINE.md` contains the required sections, allowed status vocabulary, follow-up register disposition, spec verdict, and downstream planning effect.

## Rollback/non-goals/deferred items

- Rollback: revise or remove AAM-P1 baseline docs only.
- Non-goals: no `src/`, `tests/`, schema, migration, API, eval implementation, or runtime behavior changes.
- Deferred items: implementation work belongs to AAM-P2 through AAM-P11 and must be recorded with owner phase, why deferred, blocking dependency, and acceptance gate.
</traceability>

<threat_model>
AAM-P1 is a documentation/planning phase, so it does not introduce runtime attack surface. The main risks are planning hazards that could cause unsafe later implementation:

| Threat | Impact | Mitigation in this plan | Blocking? |
| --- | --- | --- | --- |
| Target contract is misreported as already implemented | Downstream phases skip required safety work | Require current evidence paths and separate current limitation from target contract in every evidence row | yes |
| Status vocabulary drift (`N/A`, `DONE`, `TODO`) | Readiness gates become ambiguous | Require only `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, `MISSING` in every `Status` field | yes |
| Later-phase safety contracts omitted from baseline | Approval/tool/action/replay migrations proceed without guardrails | Require follow-up register disposition and phase owner mapping for every applicable item | yes |
| Source files modified during baseline | Docs-only baseline accidentally changes runtime behavior | Verification must show no `src/` or `tests/` modifications are part of AAM-P1 execution | yes |
</threat_model>

<must_haves>
- `AAM-P1-CONTRACT-BASELINE.md` contains these nine required sections exactly as headings: `## Contract Inventory`, `## Current-vs-Target Evidence Checklist`, `## Initial Coverage Matrix`, `## Spec Consistency Findings`, `## Identifier Semantics`, `## Boris/GSD Phase Notes`, `## Phase Planning Follow-up Register Disposition`, `## Review Checklist`, and `## Readiness Verdict`.
- The baseline artifact includes contract inventory rows for at least these areas: API/frontend boundary, LangGraph orchestration, AgentState lifecycle, intent/slot/clarification, Knowledge/RAG/EvidenceRefV1, Business tools/ToolCallContext/ToolResultV2, memory/session/long-term/case, approvals/SLA/risk, action draft/demo/external execution, observability/replay, migration rollout, contract tests, integration golden flows, eval gates, explicit non-goals, follow-up register.
- The baseline artifact includes spec consistency findings or an explicit no-findings statement after checking Section 19, phase decomposition, current source evidence, and AAM-P1 artifacts.
- The baseline artifact includes identifier semantics for at least `AAM-P1`, historical MOCA phase IDs, `thread_id`, `session_id`, `run_id`, `trace_id`, `approval_revision`, `action_payload_hash`, `safety_snapshot_hash`, `evidence_id`, `tool_call_id`, and `operation_id`.
- The baseline artifact includes Boris/GSD phase notes explaining that AAM-P1 is a GSD phase-level docs baseline and Boris-style review is limited to diff/scope/over-design checks.
- The baseline artifact separates current evidence from target contract for each current-vs-target row.
- The baseline artifact includes every follow-up item from `docs/agent-architecture-phase-decomposition.md` Section 6 and assigns status using allowed vocabulary.
- No row in any `Status` column uses `N/A`.
- Readiness verdict states whether AAM-P2/AAM-P3 planning may proceed and why.
</must_haves>

<tasks>

<task id="1" type="execute">
  <title>Extract AAM-P1 baseline inputs</title>
  <read_first>
  - `.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTEXT.md`
  - `.planning/phases/AAM-P1-contract-baseline/AAM-P1-RESEARCH.md`
  - `docs/agent-architecture-spec.md`
  - `docs/agent-architecture-phase-decomposition.md`
  - `docs/agent-architecture-spec-review.md`
  - `.planning/ROADMAP.md`
  - `.planning/REQUIREMENTS.md`
  - `.planning/STATE.md`
  - `src/agent/graph.py`
  - `src/agent/state.py`
  - `src/agent/tools/contracts.py`
  - `src/agent/tools/registry.py`
  - `src/rag/schemas.py`
  - `src/db/models.py`
  </read_first>
  <action>
  Build an extraction note for the baseline artifact using these exact categories:

  - API/frontend boundary.
  - LangGraph orchestration.
  - AgentState lifecycle.
  - Intent/slot/clarification.
  - Knowledge/RAG/EvidenceRefV1.
  - Business tools/ToolCallContext/ToolResultV2.
  - Memory: working/session/long-term/case.
  - Approvals/SLA/risk policy.
  - Action draft/demo/external execution.
  - Observability/replay.
  - Migration rollout protocol.
  - Contract tests.
  - Integration golden flows.
  - Eval gates.
  - Explicit non-goals.
  - Phase planning follow-up register.

  For each category, collect:

  - `Spec source` as a section name or document path.
  - `Current evidence` as concrete file paths or `No current source evidence found in listed read_first files`.
  - `Current limitation` as one sentence.
  - `Target owner phase` as one of `AAM-P1` through `AAM-P11`.
  - `Required proof` as contract test/eval/review evidence needed before marking the target contract implemented.
  </action>
  <verify>
  Confirm extraction covers all 16 categories listed in this task action.
  </verify>
  <acceptance_criteria>
  - Extraction includes the exact string `API/frontend boundary`.
  - Extraction includes the exact string `Knowledge/RAG/EvidenceRefV1`.
  - Extraction includes the exact string `Phase planning follow-up register`.
  - Extraction assigns every category to an owner phase matching regex `AAM-P[1-9][0-1]?`.
  </acceptance_criteria>
</task>

<task id="2" type="execute">
  <title>Create contract inventory section</title>
  <read_first>
  - `.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTEXT.md`
  - `.planning/phases/AAM-P1-contract-baseline/AAM-P1-RESEARCH.md`
  - `docs/agent-architecture-phase-decomposition.md`
  - `docs/agent-architecture-spec.md`
  - `src/agent/graph.py`
  - `src/agent/state.py`
  - `src/agent/tools/contracts.py`
  - `src/agent/tools/registry.py`
  - `src/rag/schemas.py`
  - `src/db/models.py`
  </read_first>
  <action>
  Create `.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTRACT-BASELINE.md` with heading `# AAM-P1 Contract Baseline` and a section `## Contract Inventory`.

  The `## Contract Inventory` section must be a markdown table with these exact columns:

  `Contract area | Spec source | Current evidence | Current limitation | Owner phase | Required proof | Migration/read-switch owner | Eval gate | Status`

  Include at least these rows and statuses:

  - `API/frontend boundary` with current evidence `src/api/routers/agent.py`, `src/api/routers/agent_runs.py`, `src/api/routers/approvals.py`, `src/api/routers/traces.py`; owner `AAM-P9` for replay/API trace compatibility where relevant; status `PARTIAL`.
  - `LangGraph orchestration` with current evidence `src/agent/graph.py`; owner `AAM-P4`; status `PARTIAL`.
  - `AgentState lifecycle` with current evidence `src/agent/state.py`; owner `AAM-P4`; status `PARTIAL`.
  - `Knowledge/RAG/EvidenceRefV1` with current evidence `src/rag/schemas.py`, `src/rag/retriever.py`, `src/rag/citation_validator.py`; owner `AAM-P2`; status `DEFERRED_WITH_OWNER`.
  - `Business tools/ToolCallContext/ToolResultV2` with current evidence `src/agent/tools/contracts.py`, `src/agent/tools/registry.py`; owner `AAM-P3`; status `DEFERRED_WITH_OWNER`.
  - `Memory/session/long-term/case` with current evidence `src/agent/state.py`; owners `AAM-P6`, `AAM-P10`; status `DEFERRED_WITH_OWNER`.
  - `Approvals/SLA/risk` with current evidence `src/agent/nodes/approval_gate.py`, `src/api/routers/approvals.py`, `src/db/models.py`; owner `AAM-P7`; status `DEFERRED_WITH_OWNER`.
  - `Action draft/demo/external execution` with current evidence `src/agent/nodes/execute_action.py`, `src/db/models.py`; owners `AAM-P8`, `AAM-P11`; status `DEFERRED_WITH_OWNER`.
  - `Observability/replay` with current evidence `src/agent/trace.py`, `src/repositories/trace_repo.py`, `src/api/routers/traces.py`, `src/db/models.py`; owner `AAM-P9`; status `DEFERRED_WITH_OWNER`.
  - `Migration rollout protocol` with current evidence `docs/agent-architecture-phase-decomposition.md`; owner `each schema owner phase`; status `PARTIAL`.
  - `Contract tests` with current evidence `tests/`; owner `every AAM phase`; status `PARTIAL`.
  - `Eval gates` with current evidence `docs/evaluation.md`; owner `relevant AAM phase`; status `PARTIAL`.
  - `Explicit non-goals` with current evidence `docs/agent-architecture-spec.md`; owner `every AAM phase`; status `COVERED`.

  Use `N/A with reason: <reason>` only in non-status fields when no migration/read-switch/eval applies.
  </action>
  <verify>
  Inspect the created file and confirm the inventory table includes the exact column header and all rows listed above.
  </verify>
  <acceptance_criteria>
  - `.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTRACT-BASELINE.md` contains `## Contract Inventory`.
  - The file contains `Contract area | Spec source | Current evidence | Current limitation | Owner phase | Required proof | Migration/read-switch owner | Eval gate | Status`.
  - The file contains `Knowledge/RAG/EvidenceRefV1` and `AAM-P2` in the same inventory row.
  - The file contains `Business tools/ToolCallContext/ToolResultV2` and `AAM-P3` in the same inventory row.
  - No inventory row marks target-only service facade work as `COVERED` unless current source evidence proves the facade exists.
  </acceptance_criteria>
</task>

<task id="3" type="execute">
  <title>Create current-vs-target evidence checklist</title>
  <read_first>
  - `.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTRACT-BASELINE.md`
  - `docs/agent-architecture-spec.md`
  - `src/agent/graph.py`
  - `src/agent/state.py`
  - `src/agent/tools/contracts.py`
  - `src/agent/tools/registry.py`
  - `src/rag/schemas.py`
  - `src/db/models.py`
  </read_first>
  <action>
  Add `## Current-vs-Target Evidence Checklist`, `## Identifier Semantics`, and `## Boris/GSD Phase Notes` to `AAM-P1-CONTRACT-BASELINE.md`.

  Use a markdown table with these exact columns:

  `Capability | Current evidence | Current limitation | Target contract | Owner phase | Proof before COVERED | Status`

  Include rows for at least:

  - `Current graph nodes and routers`.
  - `Graph path endpoints and resume semantics`.
  - `AgentState field registry and lifecycle`.
  - `Canonical EvidenceRefV1`.
  - `Current tool registry vs target ToolCallContext/ToolResultV2`.
  - `Session memory vs long-term/case memory`.
  - `Approval request/decision state machine`.
  - `ActionSafetySnapshot and canonical hash profile`.
  - `Demo action draft boundary`.
  - `External action/outbox/reconciliation`.
  - `ReplayEventV3 and run lifecycle finalizer`.
  - `Eval gates with dataset owner/version/hash`.

  Each row must explicitly say whether the current source proves implementation, partially proves implementation, or has no current source evidence in the files read.

  The `## Graph path endpoints and resume semantics` content must explicitly state:

  - Current `src/agent/graph.py` normal path ends at `final_response -> END`.
  - Current approval path routes through `approval_gate`, then `route_after_approval`; `decision == "approve"` routes to `execute_action`, and other decisions route to `final_response`.
  - Target `respond` / `needs_info`, `edit`, `expired`, `superseded`, multi-level approval, and replay-visible resume semantics are not fully proven by current graph evidence and belong to AAM-P7/AAM-P9 owner gates.

  The `## Identifier Semantics` section must define at least:

  - `AAM-P1`: Agent Architecture Migration workstream phase ID; not historical MOCA Phase 1.
  - Historical MOCA phase IDs: `.planning/ROADMAP.md` phases 1-11; not overwritten by AAM-Px.
  - `thread_id`, `session_id`, `run_id`, `trace_id`, `approval_revision`, `action_payload_hash`, `safety_snapshot_hash`, `evidence_id`, `tool_call_id`, and `operation_id`.
  - For each identifier, include `Current evidence`, `Target meaning`, `Owner phase`, and `Status`.

  The `## Boris/GSD Phase Notes` section must state:

  - AAM-P1 is controlled by GSD as a phase-level docs baseline.
  - AAM-P1 execution is docs-only and must not modify source implementation.
  - Boris-style review is limited to checking final diff scope, over-design, target-vs-current evidence discipline, and whether any source modifications slipped in.
  - Later AAM-P2/AAM-P3 planning may use Boris-style review for quality, but GSD controls phase workflow.
  </action>
  <verify>
  Confirm every row has a non-empty `Current evidence`, `Current limitation`, `Target contract`, `Owner phase`, `Proof before COVERED`, and `Status` cell.
  </verify>
  <acceptance_criteria>
  - The file contains `## Current-vs-Target Evidence Checklist`.
  - The checklist contains `Canonical EvidenceRefV1`.
  - The checklist contains `ActionSafetySnapshot and canonical hash profile`.
  - The checklist contains `ReplayEventV3 and run lifecycle finalizer`.
  - The checklist contains `Proof before COVERED`.
  - The checklist does not claim `Canonical EvidenceRefV1` is implemented solely because `src/rag/schemas.py` has `EvidenceItem`.
  </acceptance_criteria>
</task>

<task id="4" type="execute">
  <title>Create initial coverage matrix and follow-up register disposition</title>
  <read_first>
  - `.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTRACT-BASELINE.md`
  - `docs/agent-architecture-phase-decomposition.md`
  - `docs/agent-architecture-spec.md`
  </read_first>
  <action>
  Add three sections to `AAM-P1-CONTRACT-BASELINE.md`:

  1. `## Initial Coverage Matrix`
  2. `## Spec Consistency Findings`
  3. `## Phase Planning Follow-up Register Disposition`

  The `## Initial Coverage Matrix` table must use these exact columns:

  `Spec area | Covered by phase | Required tests | Migration owner | Gap / owner gate | Read-switch / rollback owner | Eval gate | Status`

  Populate the matrix using the global coverage matrix in `docs/agent-architecture-phase-decomposition.md`, adjusted for AAM-P1 baseline state. Preserve the allowed status vocabulary. For every `PARTIAL` and `DEFERRED_WITH_OWNER` row, include owner phase, non-blocking rationale, blocking dependency, and acceptance gate in `Gap / owner gate` or related non-status cells.

  The `## Spec Consistency Findings` section must compare `docs/agent-architecture-spec.md` Section 19, `docs/agent-architecture-phase-decomposition.md`, current source evidence, and AAM-P1 artifacts. Use a markdown table with these exact columns:

  `Finding | Section 19 requirement | Compared evidence | Recommended handling | Readiness impact | Owner | Status`

  If no inconsistency is found, include one row with `Finding` = `None found after checking named sources`, `Recommended handling` = `Proceed with current baseline`, `Readiness impact` = `No blocker`, `Owner` = `AAM-P1`, and `Status` = `COVERED`.

  If an inconsistency is found, do not normalize it away. Use `PARTIAL` or `MISSING` when the route is unsupported or unresolved, and use `DEFERRED_WITH_OWNER` only when a later owner phase and acceptance gate are explicit.

  The `## Phase Planning Follow-up Register Disposition` table must use these exact columns:

  `Follow-up item | Required handling | Owner / gate | AAM-P1 disposition | Status`

  Include exactly these follow-up item names from `docs/agent-architecture-phase-decomposition.md` Section 6:

  - `AAM-P1 baseline artifact names`
  - `Read-switch owner/config visibility`
  - `AAM-P7 internal slices`
  - `Cross-table enforcement row mapping`
  - `PARTIAL/deferred status discipline`
  - `Eval gate blocking status`

  Required statuses:

  - `AAM-P1 baseline artifact names`: `COVERED` if all required AAM-P1 artifact sections exist.
  - `Read-switch owner/config visibility`: `DEFERRED_WITH_OWNER` with owner `relevant schema owner phase` and AAM-P1 baseline visibility requirement.
  - `AAM-P7 internal slices`: `DEFERRED_WITH_OWNER` with owner `AAM-P7`.
  - `Cross-table enforcement row mapping`: `DEFERRED_WITH_OWNER` with owners `AAM-P7/AAM-P8/AAM-P11`.
  - `PARTIAL/deferred status discipline`: `COVERED` only if every partial/deferred row names owner/rationale/gate.
  - `Eval gate blocking status`: `PARTIAL` if the baseline names the requirement but exact dataset owner/version/hash remain phase-owned.
  </action>
  <verify>
  Confirm all six follow-up item names appear exactly once in the follow-up disposition table.
  </verify>
  <acceptance_criteria>
  - The file contains `## Initial Coverage Matrix`.
  - The file contains `## Spec Consistency Findings`.
  - The file contains `## Phase Planning Follow-up Register Disposition`.
  - The file contains `AAM-P1 baseline artifact names`.
  - The file contains `Read-switch owner/config visibility`.
  - The file contains `Cross-table enforcement row mapping`.
  - The file contains `Eval gate blocking status`.
  - No `Status` cell in these sections contains `N/A`.
  </acceptance_criteria>
</task>

<task id="5" type="execute">
  <title>Create review checklist and readiness verdict</title>
  <read_first>
  - `.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTRACT-BASELINE.md`
  - `docs/agent-architecture-phase-decomposition.md`
  </read_first>
  <action>
  Add these sections to `AAM-P1-CONTRACT-BASELINE.md`:

  1. `## Review Checklist`
  2. `## Readiness Verdict`

  The `## Review Checklist` section must include checklist items for:

  - Artifact names use `AAM-P1` and not bare `Phase 1`.
  - Current evidence is separated from target contracts.
  - Spec consistency findings are present and conflicts are not silently normalized or forced to `COVERED`.
  - Every `PARTIAL` row names owner, non-blocking rationale, blocking dependency, and acceptance gate.
  - Every `DEFERRED_WITH_OWNER` row names owner phase and acceptance gate.
  - No `Status` cell uses `N/A`.
  - AAM-P1 execution is docs-only and changes no `src/`, `tests/`, schema, migration, or API contract files.
  - AAM-P2/AAM-P3 planning can consume the baseline without rereading the entire spec.

  The `## Readiness Verdict` section must include:

  - `Verdict:` with one of `PASS`, `PARTIAL`, or `BLOCKED`.
  - `Downstream planning status:` with one of `READY_FOR_AAM-P2_P3_PLANNING`, `PARTIAL_WITH_DEFERRED_OWNER_GATES`, or `BLOCKED_MISSING_BASELINE`.
  - `Downstream effect:` describing whether AAM-P2 and AAM-P3 planning may proceed.
  - `Blocking rule:` stating that any `MISSING` in relevant AAM-P1 outputs blocks downstream planning.
  - `Status counts:` with counts for `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, `MISSING`.
  - `Known limitations:` describing that the baseline is not implementation proof for later target contracts.
  </action>
  <verify>
  Confirm `Verdict:` exists and does not say downstream target contracts are implemented.
  </verify>
  <acceptance_criteria>
  - The file contains `## Review Checklist`.
  - The file contains `## Readiness Verdict`.
  - The file contains `Verdict:`.
  - The file contains `Downstream effect:`.
  - The file contains `Blocking rule:`.
  - The file contains `Status counts:`.
  - The file contains `Known limitations:`.
  </acceptance_criteria>
</task>

<task id="6" type="execute">
  <title>Validate AAM-P1 baseline artifact</title>
  <read_first>
  - `.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTRACT-BASELINE.md`
  - `.planning/phases/AAM-P1-contract-baseline/AAM-P1-01-PLAN.md`
  </read_first>
  <action>
  Run deterministic documentation checks from repository root:

  ```bash
  python - <<'PY'
  from pathlib import Path
  p = Path('.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTRACT-BASELINE.md')
  text = p.read_text()
  required = [
      '## Contract Inventory',
      '## Current-vs-Target Evidence Checklist',
      '## Initial Coverage Matrix',
      '## Spec Consistency Findings',
      '## Identifier Semantics',
      '## Boris/GSD Phase Notes',
      '## Phase Planning Follow-up Register Disposition',
      '## Review Checklist',
      '## Readiness Verdict',
  ]
  missing = [h for h in required if h not in text]
  followups = [
      'AAM-P1 baseline artifact names',
      'Read-switch owner/config visibility',
      'AAM-P7 internal slices',
      'Cross-table enforcement row mapping',
      'PARTIAL/deferred status discipline',
      'Eval gate blocking status',
  ]
  missing_followups = [f for f in followups if text.count(f) == 0]
  allowed = {'COVERED', 'PARTIAL', 'DEFERRED_WITH_OWNER', 'MISSING'}
  bad_status_lines = []
  for line in text.splitlines():
      if '|' not in line or line.strip().startswith('| ---'):
          continue
      cells = [c.strip() for c in line.strip().strip('|').split('|')]
      if cells and cells[-1] in allowed:
          continue
      if cells and cells[-1] == 'Status':
          continue
      if len(cells) >= 2 and cells[-1] == 'N/A':
          bad_status_lines.append(line)
  if missing or missing_followups or bad_status_lines:
      print({'missing_sections': missing, 'missing_followups': missing_followups, 'bad_status_lines': bad_status_lines})
      raise SystemExit(1)
  print('AAM-P1 baseline doc checks passed')
  PY
  ```

  Then run:

  ```bash
  git status --short
  ```

  Confirm AAM-P1 execution did not modify `src/`, `tests/`, `src/db/migrations/`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, or `.planning/STATE.md`.
  </action>
  <verify>
  Documentation check prints `AAM-P1 baseline doc checks passed`, and git status shows only AAM-P1 planning artifacts changed/created for this phase.
  </verify>
  <acceptance_criteria>
  - The Python check exits 0 and prints `AAM-P1 baseline doc checks passed`.
  - `git status --short` does not list modified `src/` files from AAM-P1 execution.
  - `git status --short` does not list modified `tests/` files from AAM-P1 execution.
  - `git status --short` does not list modified `src/db/migrations/` files from AAM-P1 execution.
  - `git status --short` does not list modified `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, or `.planning/STATE.md` from AAM-P1 execution.
  </acceptance_criteria>
</task>

</tasks>

<verification>
From repository root, run the Task 6 Python check and `git status --short`. Review `AAM-P1-CONTRACT-BASELINE.md` manually against this plan's must-haves.
</verification>

<success_criteria>
- `.planning/phases/AAM-P1-contract-baseline/AAM-P1-CONTRACT-BASELINE.md` exists.
- The baseline document contains the nine required sections.
- Every follow-up register item is dispositioned.
- Spec consistency findings are present; conflicts with Section 19 are either raised or explicitly reported as not found after named-source checks.
- `Status` cells use only `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, or `MISSING`.
- The readiness verdict uses `PASS`, `PARTIAL`, or `BLOCKED` and explicitly controls whether AAM-P2/AAM-P3 planning can proceed.
- No source implementation files are modified by AAM-P1.
</success_criteria>

## PLANNING COMPLETE

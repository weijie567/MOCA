---
phase: 16
plan: 01
type: tdd
wave: 1
depends_on: []
files_modified:
  - src/memory/identity.py
  - src/memory/schemas.py
  - tests/memory/test_memory_identity.py
autonomous: true
requirements:
  - MEMID-01
  - MEMEVAL-01
must_haves:
  - "`memory_identity.v1` computes stable `sha256:` hashes."
  - "Tenant, memory type, scope type, scope id, and content hash participate in canonical identity and candidate identity."
  - "Source fallback accepts only the authoritative `MemorySourceRefV1` typed key set."
  - "Tests cover content hash, candidate hash, source hash stability, unknown key rejection, and authority-boundary imports."
---

# Plan 16-01: memory_identity.v1

<objective>
Add `memory_identity.v1` canonical normalization and stable content/source hashing for long-term memories, case memories, tombstones, and candidate write events.
</objective>

<threat_model>
- T-16-01-01 tenant_cross_scope_hash_collision: identity inputs must include tenant/scope/memory type fields so two tenants or scopes cannot share an active tombstone or memory identity. Severity: high. Mitigation: tests require tenant/scope/type fields in hash input.
- T-16-01-02 arbitrary_source_ref_rewrite: arbitrary JSON keys in source identity could bypass tombstones or create unauditable source matches. Severity: high. Mitigation: reject source refs outside the authoritative `MemorySourceRefV1` typed key set.
- T-16-01-03 unstable_normalization: whitespace, Unicode casing, unordered mappings, or datetime formatting drift could make tombstone matching nondeterministic. Severity: medium. Mitigation: golden tests for normalized content/source hashes.
- T-16-01-04 authority_confusion: identity helpers must not import or emit `EvidenceRefV1`, approval evidence, or action authorization structures. Severity: high. Mitigation: boundary grep tests.
</threat_model>

<tasks>
<task id="16-01-01" type="tdd">
<name>Add memory identity golden tests</name>
<files>src/memory/identity.py, src/memory/schemas.py, tests/memory/test_memory_identity.py</files>
<read_first>
- src/common/canonical_hash.py
- tests/approvals/test_canonical_hash.py
- .planning/phases/16-long-term-case-memory/16-CONTEXT.md
- .planning/phases/16-long-term-case-memory/16-RESEARCH.md
</read_first>
<action>
Create `tests/memory/test_memory_identity.py` with failing tests for `memory_identity.v1`. Include exact cases for:
- `normalize_memory_content("  Refund  policy\npreference  ")` returns `"refund policy preference"`.
- `canonical_memory_content_hash(memory_type="long_term_fact", content="Refund policy preference")` returns a string matching `^sha256:[0-9a-f]{64}$`.
- identical content with extra whitespace produces the same hash.
- different `memory_type` values produce different hashes for the same content.
- `canonical_memory_candidate_hash(tenant_id=..., memory_type=..., scope_type=..., scope_id=..., content_hash=..., source_identity_hash=...)` returns a string matching `^sha256:[0-9a-f]{64}$`.
- candidate hash is stable for the same candidate envelope and changes when `tenant_id`, `memory_type`, `scope_type`, `scope_id`, `content_hash`, or `source_identity_hash` changes.
- candidate hash does not accept raw payload, raw tool output, full policy text, approval/action authority bodies, or replay/debug blobs as inputs.
- `canonical_source_identity_hash(...)` accepts only the authoritative `MemorySourceRefV1` keys: `source_type`, `run_id`, `event_id`, `conversation_message_id`, `tool_result_id`, `agent_run_id`, `business_object_type`, `business_object_id`, `policy_version`, and `outcome_id`.
- `canonical_source_identity_hash({"random_json_key": "x"})` raises `MemoryIdentityError`.
</action>
<acceptance_criteria>
- `tests/memory/test_memory_identity.py` contains `def test_memory_content_hash_is_stable_across_whitespace`.
- `tests/memory/test_memory_identity.py` contains `def test_memory_candidate_hash_binds_scope_content_and_source_identity`.
- `tests/memory/test_memory_identity.py` contains `def test_source_identity_rejects_unknown_keys`.
- Running `uv run pytest tests/memory/test_memory_identity.py -q` fails before implementation and passes after implementation.
</acceptance_criteria>
<done>All acceptance criteria for 16-01-01 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_identity.py -q
</verify>
</task>

<task id="16-01-02" type="execute">
<name>Implement memory identity helpers</name>
<files>src/memory/identity.py, src/memory/schemas.py, tests/memory/test_memory_identity.py</files>
<read_first>
- src/common/canonical_hash.py
- src/memory/schemas.py
- tests/memory/test_memory_identity.py
</read_first>
<action>
Add `src/memory/identity.py` with:
- `MEMORY_IDENTITY_VERSION = "memory_identity.v1"`
- `ALLOWED_SOURCE_REF_KEYS = frozenset({"source_type", "run_id", "event_id", "conversation_message_id", "tool_result_id", "agent_run_id", "business_object_type", "business_object_id", "policy_version", "outcome_id"})`
- `class MemoryIdentityError(ValueError)`
- `normalize_memory_content(content: str) -> str`
- `canonical_memory_content_hash(*, memory_type: str, content: str) -> str`
- `canonical_memory_identity_hash(*, tenant_id: str, memory_type: str, scope_type: str, scope_id: str, content_hash: str) -> str`
- `canonical_source_identity_hash(source_ref: Mapping[str, Any]) -> str | None`
- `canonical_memory_candidate_hash(*, tenant_id: str, memory_type: str, scope_type: str, scope_id: str, content_hash: str, source_identity_hash: str | None = None) -> str`
Use `src.common.canonical_hash.canonical_hash` with explicit `schema_version` values and allowed field sets. `source_type` is the typed discriminator for source identity; run/event/business/policy/outcome keys are optional but only the listed keys are allowed. Candidate hash is the stable write-event/candidate envelope hash over `tenant_id`, `memory_type`, `scope_type`, `scope_id`, `content_hash`, and nullable `source_identity_hash`; it reuses `content_hash` and `source_identity_hash` and must not accept raw payload fields. Reject unknown keys deterministically and reject bare floats through the shared canonical hash behavior.
</action>
<acceptance_criteria>
- `src/memory/identity.py` contains `MEMORY_IDENTITY_VERSION = "memory_identity.v1"`.
- `src/memory/identity.py` contains `ALLOWED_SOURCE_REF_KEYS`.
- `src/memory/identity.py` contains `source_type`, `run_id`, `event_id`, `business_object_type`, `policy_version`, and `outcome_id` in the allowed source key set.
- `src/memory/identity.py` contains `canonical_memory_identity_hash`.
- `src/memory/identity.py` contains `canonical_memory_candidate_hash`.
- `src/memory/identity.py` contains `canonical_source_identity_hash`.
- `src/memory/identity.py` does not contain `EvidenceRefV1`, `ApprovalRequest`, or `ActionDraft`.
- `uv run pytest tests/memory/test_memory_identity.py -q` exits 0.
</acceptance_criteria>
<done>All acceptance criteria for 16-01-02 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_identity.py -q
</verify>
</task>

<task id="16-01-03" type="execute">
<name>Add prompt-safe identity schemas</name>
<files>src/memory/identity.py, src/memory/schemas.py, tests/memory/test_memory_identity.py</files>
<read_first>
- src/memory/schemas.py
- src/memory/identity.py
- tests/memory/test_memory_identity.py
</read_first>
<action>
Add Pydantic input schemas in `src/memory/schemas.py` only if useful for downstream services:
- `MemorySourceRefV1` with the same authoritative optional key set used by `ALLOWED_SOURCE_REF_KEYS`: `source_type`, `run_id`, `event_id`, `conversation_message_id`, `tool_result_id`, `agent_run_id`, `business_object_type`, `business_object_id`, `policy_version`, and `outcome_id`.
- `MemoryIdentityV1` with `tenant_id`, `memory_type`, `scope_type`, `scope_id`, `content_hash`, `source_identity_hash`.
- `MemoryCandidateIdentityV1` with `tenant_id`, `memory_type`, `scope_type`, `scope_id`, `content_hash`, nullable `source_identity_hash`, and `candidate_hash`.
Keep these schemas prompt-safe and do not add raw payload, policy evidence, approval authority, action authority, or replay body fields.
</action>
<acceptance_criteria>
- If `MemorySourceRefV1` is added, `src/memory/schemas.py` contains no field named `raw_payload`, `policy_evidence`, `approval_authority_body`, or `action_authority_body`.
- If `MemoryCandidateIdentityV1` is added, it contains `candidate_hash` and no raw payload/body fields.
- `uv run pytest tests/memory/test_memory_identity.py -q` exits 0.
</acceptance_criteria>
<done>All acceptance criteria for 16-01-03 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_identity.py -q
</verify>
</task>
</tasks>

<verification>
- Run `uv run pytest tests/memory/test_memory_identity.py -q`.
- Run `uv run ruff check src/memory/identity.py tests/memory/test_memory_identity.py`.
</verification>

<success_criteria>
- `memory_identity.v1` helpers exist and are deterministic.
- `candidate_hash` is generated only by `canonical_memory_candidate_hash` from the stable candidate envelope and reuses `content_hash` / `source_identity_hash`.
- Unknown source identity keys are rejected.
- Source identity fallback is limited to the authoritative typed `MemorySourceRefV1` key set.
- Identity helpers do not import evidence, approval, action, or replay authority structures.
</success_criteria>

<must_haves>
- `memory_identity.v1` computes stable `sha256:` hashes.
- Tenant, memory type, scope type, scope id, and content hash participate in canonical identity and candidate identity.
- Source fallback accepts only the authoritative `MemorySourceRefV1` typed key set.
- Tests cover content hash, candidate hash, source hash stability, unknown key rejection, and authority-boundary imports.
</must_haves>

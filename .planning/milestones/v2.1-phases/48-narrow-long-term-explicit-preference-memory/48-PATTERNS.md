# Phase 48: Narrow Long-Term Explicit Preference Memory - Pattern Map

**Mapped:** 2026-07-04
**Mode:** local orchestrator fallback
**Reason:** The current client did not expose the `gsd-pattern-mapper` subagent; this map is based on direct repository inspection.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `docs/contract-spec.md` | contract | transform | Sections 13.3, 13.5, 13.6 | exact |
| `docs/architecture-overview.md` | contract | transform | memory architecture rows | exact |
| `docs/memory-contract-delta.md` | contract | transform | memory delta table | exact |
| `.planning/MEMORY-REDESIGN-DECISIONS.md` | planning decision log | transform | Phase 45-47 trace entries | exact |
| `tests/memory/test_phase48_long_term_preference_alignment.py` | static tests | transform | `test_phase47_case_precedent_alignment.py` | role-match |
| `tests/architecture/test_memory_contract_delta.py` | static tests | transform | current memory delta guards | exact |
| `src/memory/policy.py` | policy utility | transform | existing long-term/case source policy | exact |
| `src/memory/schemas.py` | schema | validation | existing `LongTermMemoryWriteCandidate` | exact |
| `src/memory/long_term.py` | service | CRUD + audit | existing tombstone/PII/duplicate branches | exact |
| `src/memory/repository.py` | repository | CRUD + retrieval | existing published prompt-safe filters | exact |
| `src/memory/semantic_episode.py` | projection utility | transform | existing semantic candidate projector | exact |
| `src/memory/write_service.py` | write facade | transform + routing | existing explicit candidate coercion | exact |
| `src/memory/preference_capture.py` | new utility/service | transform | `write_service.py` PII helpers + policy module | composite |
| `src/agent/nodes/memory_write.py` | graph node | side-effect orchestration | existing MemoryWriteService construction | exact |
| `src/api/routers/memory.py` | API router | request-response | existing memory review endpoints | exact |
| `src/api/schemas/memory.py` | API schema | validation | existing review action schema | exact |
| `src/auth/jwt.py` | auth config | validation | existing `ROLE_SCOPES` | exact |
| `src/auth/permissions.py` | auth config | validation | OAuth2 scope registry | exact |

## Pattern Assignments

### Contract Static Tests

**Analog:** `tests/memory/test_phase47_case_precedent_alignment.py`

Use static tests to lock:

- `docs/contract-spec.md` Section 13.3 says `explicit preference memory only`.
- `long_term_memories`, `case_memories`, `session_memories`, `case_working_contexts`, `conversation_threads.case_id`, and `thread_case_links` are not renamed or dropped by Phase 48.
- Phase 48 plan verification commands use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest`.
- `docs/memory-contract-delta.md` no longer preserves old deterministic durable-fact auto-publish semantics as target state.

### Long-Term Source Policy

**Analog:** current `src/memory/policy.py`

Keep the `MemoryPolicyDecision` shape:

```python
class MemoryPolicyDecision(BaseModel):
    memory_type: MemoryPolicyMemoryType
    decision: Literal["write", "needs_review", "skip"]
    review_status: str | None = None
    reason_code: str
    policy_version: str = MEMORY_POLICY_VERSION
    blocked_by: list[str] = Field(default_factory=list)
    authority_class: Literal["contextual_only"] = MEMORY_POLICY_AUTHORITY_CLASS
```

Add explicit allowlists:

```python
PUBLISHED_LONG_TERM_SOURCE_TYPES = frozenset(
    {"explicit_user_preference", "explicit_admin_preference", "human_reviewed"}
)
REVIEW_REQUIRED_LONG_TERM_SOURCE_TYPES = frozenset({"semantic_episode_candidate"})
```

When a long-term source is no longer allowed, return `decision="skip"`, `reason_code="source_type_not_allowed"`, and `blocked_by=["source_type_not_allowed"]`. The service must honor this skip before insertion.

### Long-Term Service Skip Branch

**Analog:** `LongTermMemoryService.write_memory(...)` PII and tombstone branches.

The service already emits skip events for tombstones and PII. Use the same result shape for:

- `memory_kind != "preference"` with reason `not_preference_memory_kind`.
- policy decision `skip` with reason `source_type_not_allowed`.
- hard-rule content rejected by the preference capture helper before candidate construction where possible.

Do not insert a row for skipped policy decisions.

### Semantic Episode Projection

**Analog:** existing `project_semantic_episode_candidates(...)`

Keep `SemanticEpisodeCandidate` and `source_type="semantic_episode_candidate"` for the needs-review candidate queue, but only emit `kind="preference_candidate"`. Non-preference keys are ignored:

- `cross_case_patterns`
- `similar_cases`
- `strategy_hints`

### Explicit User Preference Capture

**New helper:** `src/memory/preference_capture.py`

Recommended public functions:

```python
def detect_explicit_preference_intent(text: str) -> ExplicitPreferenceIntent | None: ...

def build_explicit_user_preference_candidate(
    state: Mapping[str, Any],
    *,
    trusted_context: Any | None = None,
) -> LongTermMemoryWriteCandidate | None: ...

def validate_soft_preference_text(text: str) -> PreferenceValidationResult: ...
```

Use deterministic phrases only. Do not call an LLM.

### Admin Save API

**Analog:** `src/api/routers/memory.py` review endpoints.

Use the existing router and response shape. Add stricter guard:

- Security scope: `memory:write`
- Role: `admin` only
- Endpoint: `POST /api/v1/memory/long-term/preferences`
- Source type: `explicit_admin_preference`
- Review status: auto-approved through `LongTermMemoryService.write_memory(...)`
- Tenant scope: only when `scope_id == str(user.tenant_id)`
- Merchant scope: require the merchant row belongs to `user.tenant_id`

### Retrieval

**Analog:** `LongTermMemoryRepository.retrieve_profile_memory(...)`

Add filters to existing retrieval predicate:

```python
LongTermMemory.memory_kind == "preference"
LongTermMemory.source_type.in_(tuple(PUBLISHED_LONG_TERM_SOURCE_TYPES))
```

Keep existing filters for review status, prompt-safe PII, tombstone, `is_current`, deletion, expiry, tenant, and scope.

### Approval Publishing

**Analog:** `LongTermMemoryService.approve_memory(...)`

Before approving a pending long-term row:

- require `memory.memory_kind == "preference"`;
- set `memory.source_type = "human_reviewed"`;
- update `memory.source_ref_json["source_type"] = "human_reviewed"` while preserving existing run/event IDs;
- then mark `review_status="approved"` and `is_current=True`.

This prevents `semantic_episode_candidate` from becoming a published prompt source.

## Anti-Patterns

- Do not add broad LLM inference from ordinary chat.
- Do not create tenant-scope preference from ordinary chat.
- Do not use semantic episode pattern/strategy/similar-case outputs as long-term rows.
- Do not rename/drop/retype `long_term_memories` or `memory_type='long_term_fact'`.
- Do not turn soft preferences into policy rules or action authorization.
- Do not use bare `pytest` in plans, docs, or verification.

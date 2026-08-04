# Phase 48: Narrow Long-Term Explicit Preference Memory - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `48-CONTEXT.md`; this log preserves alternatives considered.

**Date:** 2026-07-04
**Phase:** 48-narrow-long-term-explicit-preference-memory
**Areas discussed:** Write Entry And Source Policy, Preference Semantic Boundary, Retrieval And Scope Behavior, Governance And Interfaces

---

## Write Entry And Source Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Chat + admin + reviewed candidate | User explicit remember intent, admin save, and reviewed candidate all supported. | Yes |
| Admin/review only | No chat memory intent parsing in Phase 48. | |
| Internal candidate only | Lock service/test boundary only, no user/admin entry point. | |

**User's choice:** Chat + admin + reviewed candidate.
**Notes:** Chat accepts only explicit memory intent such as "remember this preference" or "use this going forward"; ordinary statements are not preferences.

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit user/admin/human reviewed auto-publish when safe | Non-PII, non-tombstoned, scope-valid soft preferences can publish. | Yes |
| Explicit user preference requires review | Every explicit user preference enters review first. | |
| Only admin/human reviewed can modify | User writes are more restricted. | |

**User's choice:** Explicit user preference may auto-publish.
**Notes:** Forcing needs-review after the user explicitly says "remember this preference" would hurt experience. Corrections must still use supersede/tombstone/audit.

| Option | Description | Selected |
|--------|-------------|----------|
| Merchant/team default; tenant admin-only | Merchant/team is default; tenant-level requires explicit admin save. | Yes |
| User preference first-class | Add user-specific preference as a main path. | |
| Tenant-only | Store all preferences at tenant scope. | |

**User's choice:** Merchant/team default; tenant admin-only.
**Notes:** User-specific preference is deferred because it complicates scope precedence, privacy, and conflict governance.

| Option | Description | Selected |
|--------|-------------|----------|
| Published long-term only explicit_user_preference / explicit_admin_preference / human_reviewed | Published source types are narrowed. | Yes |
| Allow semantic_episode_candidate preference needs_review | Keep a candidate exception. | Yes, as an exception |
| Keep current broad policy with extra tests | Retain deterministic tool/outcome/pattern source types. | |

**User's choice:** Published long-term memory only stores explicit and human-confirmed preferences, with a candidate queue exception.
**Notes:** `semantic_episode_candidate` may produce needs-review preference candidates, but approved/published rows must become `human_reviewed`, not remain `semantic_episode_candidate`.

---

## Preference Semantic Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Communication/display/collaboration preferences only | Keep preferences very narrow. | |
| Soft operational preferences allowed but never hard rules | Allow handling tendencies as hints, not rules. | Yes |
| Reviewed operational constraints allowed as preference hints | Broader reviewed constraints may appear as hints. | |

**User's choice:** Allow soft operational preferences, not hard rules.
**Notes:** Example allowed: low-amount refund scenarios prefer calming explanatory wording. Example forbidden: below X yuan must refund/reject.

| Option | Description | Selected |
|--------|-------------|----------|
| Only preference_candidate can project into long-term | semantic episode can only emit preference candidates. | Yes |
| All semantic episode kinds may create needs_review but only preferences can publish | Broader candidate queue. | |
| Disable semantic_episode -> long-term entirely | No automatic candidate exception. | |

**User's choice:** semantic episode only projects `preference_candidate`.
**Notes:** `cross_case_pattern`, `similar_case_hint`, and `strategy_hint` must not enter long-term memory.

---

## Retrieval And Scope Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Keep needs_long_term_memory / memory_context_load seam | Reuse existing seam and narrow returned rows. | Yes |
| Retrieve before every recommendation/response generation | Always fetch preferences. | |
| Retrieve only when intent explicitly requests preference context | Fetch only explicit memory/preference intents. | |

**User's choice:** Keep the existing seam.
**Notes:** Do not query every turn due to prompt noise/cost. Do not rely only on explicit preference intents because generation scenarios may still need hints.

| Option | Description | Selected |
|--------|-------------|----------|
| Do not add user-specific main path | Merchant/team default plus admin tenant preference only. | Yes |
| Support user scope only for personal display/communication preferences | Limited user scope. | |
| Support user scope equally with merchant scope | Full user preference path. | |

**User's choice:** Do not add user-specific preference in Phase 48.
**Notes:** User-specific preference is a post-Phase 48 defer.

---

## Governance And Interfaces

| Option | Description | Selected |
|--------|-------------|----------|
| Add minimal admin-only save API/service | Directly create `explicit_admin_preference`. | Yes |
| Reuse pending review API only | No creation endpoint. | |
| Service/internal API only; HTTP API deferred | No HTTP surface in Phase 48. | |

**User's choice:** Add minimal admin-only save API/service.
**Notes:** Permissions, scope, and audit must be explicit. Admin-created preferences are not pending review.

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic explicit phrase gate | Match only clear remember/preference phrases. | Yes |
| LLM can propose preference candidate with review | LLM inference allowed but gated. | |
| No chat recognition; upstream explicit candidates only | No chat entry. | |

**User's choice:** Deterministic explicit phrase gate.
**Notes:** No LLM inference from ordinary chat. Hits still go through PII/scope/tombstone/source validation.

| Option | Description | Selected |
|--------|-------------|----------|
| supersede / tombstone; no auto-merge | Corrections supersede, delete/forget tombstones. | Yes |
| append all and sort latest first | Let retrieval ordering handle conflicts. | |
| conflict always requires review | Any conflict blocks auto-publish. | |

**User's choice:** supersede / tombstone; no auto-merge.
**Notes:** Similar preferences may not be equivalent; auto-merge risks inventing a hard rule.

| Option | Description | Selected |
|--------|-------------|----------|
| Rewrite Section 13.3 to explicit preference-only and sync docs/tests | Narrow the normative target contract. | Yes |
| Add MVP scope note only | Keep broad target state, annotate MVP. | |
| Do not edit spec; tests only | Avoid spec changes. | |

**User's choice:** Rewrite `docs/contract-spec.md` Section 13.3.
**Notes:** This is not only an MVP annotation. Phase 48's core goal is to narrow long-term semantics, so the normative target contract must narrow too.

---

## the agent's Discretion

- Exact deterministic phrase list and normalization implementation.
- Exact admin save route/service naming.
- Exact additional preference topic/category metadata if planning proves it is needed.
- Exact plan split, provided spec alignment, source policy, write paths, retrieval behavior, and validation stay bounded.

## Deferred Ideas

- User-specific preference scope and precedence rules - post-Phase 48.
- Rich preference management UI - future product phase.
- LLM-based broad preference inference from ordinary chat - separate future review/eval design only.

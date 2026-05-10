# Coding Conventions

**Analysis Date:** 2026-05-09

## Naming Patterns

**Current repository patterns:**
- Canonical planning files use uppercase names such as `PROJECT.md` and `ROADMAP.md`
- Supporting prose documents use kebab-case such as `deep-research-report.md`
- Requirement identifiers use uppercase prefixes such as `AGNT`, `RAG`, `SAFE`, `INFR`, and `FRNT`

**Not yet established:**
- Source file naming
- Test naming
- API module layout
- Frontend component naming

## Code Style

**Current state:**
- No formatter config detected
- No linter config detected
- No type-checker config detected
- No commit hooks or CI quality gates detected

**Documentation style currently observed:**
- Markdown-heavy
- Mixed English and Chinese content across files
- Strong use of checklist and requirement-ID structure

## Import Organization

**Current state:**
- Not applicable because no source code exists

**Recommendation for first scaffold:**
- Define import ordering in formatter/linter config on day one
- Avoid letting backend and frontend adopt incompatible style defaults

## Error Handling

**Current state:**
- No executable error-handling conventions exist yet

**Documented expectations:**
- `.planning/REQUIREMENTS.md` already expects explicit error codes, evidence refusal paths, and approval gating
- These expectations should become shared utility patterns, not ad hoc route-level decisions

## Logging

**Current state:**
- No application logging framework exists yet

**Documented expectations:**
- Run IDs, trace IDs, tool call IDs, latency, token usage, and error codes are required by the planning docs
- This should become a structured logger contract early in Phase 1

## Comments

**Current documentation patterns:**
- Most prose explains intent and rationale rather than implementation details
- The strongest reusable style is requirement traceability, not low-level commentary

**Recommendation:**
- Keep this bias when code starts: explain business invariants and risk decisions, not trivial mechanics

## Function Design

**Current state:**
- No code functions to analyze

**Recommendation baseline:**
- Use schema-first interfaces for tools and APIs
- Keep LangGraph node functions narrow and explicit so execution traces stay readable

## Module Design

**Current state:**
- No modules yet

**Recommendation baseline:**
- Split by domain capability (`orders`, `refunds`, `approvals`, `rag`, `agent_runs`) rather than by framework artifact alone
- Centralize shared contracts for tool schemas, evidence models, and audit events

## Convention Risks

- The repo already mixes Chinese requirement content with English framing docs; without an explicit language policy, naming and API text will drift
- Planning rigor is high, but engineering conventions are still undefined; if Phase 1 begins without linting, formatting, and schema rules, later phases will inherit inconsistency

---
*Convention analysis: 2026-05-09*
*Update when the first application scaffold establishes real coding style*

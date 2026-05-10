# Codebase Structure

**Analysis Date:** 2026-05-09

## Directory Layout

```text
MOCA/
├── .claude/                 # Local workflow permissions
├── .git/                    # Git metadata
├── .planning/               # Project planning artifacts
│   └── research/            # Research summaries generated from the initial exploration
├── deep-research-report.md  # Main long-form solution report
└── .DS_Store                # Unwanted macOS Finder artifact
```

## Directory Purposes

**`.planning/`:**
- Purpose: Central source of truth for project framing, requirements, roadmap, and state
- Contains: `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, and research notes
- Key files: `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`
- Subdirectories: `.planning/research/`

**`.planning/research/`:**
- Purpose: Condensed research outputs that informed project initialization
- Contains: `ARCHITECTURE.md`, `FEATURES.md`, `PITFALLS.md`, `STACK.md`, `SUMMARY.md`
- Key files: `.planning/research/SUMMARY.md`
- Subdirectories: none

**`.claude/`:**
- Purpose: Local tool permission settings
- Contains: `settings.local.json`
- Key files: `.claude/settings.local.json`
- Subdirectories: none detected

## Key File Locations

**Entry Points:**
- `deep-research-report.md` - Original concept and architecture source document
- `.planning/PROJECT.md` - Project definition and core value
- `.planning/STATE.md` - Active phase tracking

**Configuration:**
- `.claude/settings.local.json` - Local workflow permissions

**Core Logic:**
- None yet; there is no `src/`, `app/`, `backend/`, `frontend/`, or `services/` directory

**Testing:**
- None yet; there is no `tests/`, `__tests__/`, or CI workflow directory

**Documentation:**
- `deep-research-report.md` - Long-form strategy document
- `.planning/*.md` - Structured planning documents

## Naming Conventions

**Files:**
- Uppercase `.md` names inside `.planning/` for canonical planning docs
- Mixed naming overall: root uses `deep-research-report.md`, while planning docs use uppercase
- No established convention for future source files yet

**Directories:**
- Dot-prefixed directories for local metadata and planning state
- No feature or package directory convention established yet

**Special Patterns:**
- Requirement IDs follow `PREFIX-##` format in `.planning/REQUIREMENTS.md`
- Phase numbers are plain integers in `.planning/ROADMAP.md`

## Where to Add New Code

**Recommended backend/API location:**
- `apps/api/` or `backend/`

**Recommended frontend location:**
- `apps/web/` or `frontend/`

**Recommended shared assets:**
- `packages/shared/` or `shared/` for schemas, DTOs, and common types

**Recommended tests:**
- `tests/` for integration/e2e
- colocated unit tests or `apps/api/tests/` and `apps/web/tests/`

**Important note:**
- Pick the structure before Phase 1 implementation starts; changing directory strategy mid-build will create unnecessary churn

## Special Directories

**`.planning/`:**
- Purpose: Generated and manually curated project-management artifacts
- Source: GSD workflows plus manual edits
- Committed: Yes

**`.git/`:**
- Purpose: Repository metadata
- Source: Git
- Committed: Not as project content

---
*Structure analysis: 2026-05-09*
*Update once real source, infra, and test directories are introduced*

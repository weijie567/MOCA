# Technology Stack

**Analysis Date:** 2026-05-09

## Languages

**Primary:**
- Markdown - Nearly all repository content lives in planning and research documents such as `deep-research-report.md` and `.planning/*.md`

**Secondary:**
- JSON - Local tool configuration in `.claude/settings.local.json`

## Runtime

**Environment:**
- No application runtime is present yet; there is no backend, frontend, worker, or CLI source tree in the repository
- Current executable dependency is the local GSD workflow tooling invoked via `gsd-sdk query ...`

**Package Manager:**
- None detected
- Lockfile: none present

## Frameworks

**Current:**
- GSD planning workflow - Used to generate and manage `.planning/` artifacts

**Planned (documented, not implemented):**
- LangGraph - Agent orchestration target described in `.planning/PROJECT.md`
- FastAPI - API layer target described in `.planning/PROJECT.md`
- PostgreSQL + pgvector - Primary persistence target described in `.planning/PROJECT.md`
- Redis - Cache and rate-limiting target described in `.planning/PROJECT.md`
- React/Next.js - Frontend target described in `.planning/PROJECT.md`

## Key Dependencies

**Current:**
- `gsd-sdk` - Project workflow initialization and metadata queries
- Git - Source control only; no build or test toolchain detected

**Missing but expected soon:**
- Project manifest such as `package.json` or `pyproject.toml`
- Dependency lockfile
- Docker Compose definition for the planned local stack
- Environment example such as `.env.example`

## Configuration

**Environment:**
- No application environment variables are defined yet
- Local workflow permissions live in `.claude/settings.local.json`

**Build:**
- No build configuration files detected
- No formatter, linter, or type-checker configuration detected

## Platform Requirements

**Development (current state):**
- Any platform capable of editing Markdown and running Git
- GSD tooling available in the local Codex/Claude environment

**Development (target state):**
- Docker and Docker Compose for local services
- Python and/or Node.js once implementation begins

**Production:**
- Not applicable yet; deployment targets are only described at the planning level

---
*Stack analysis: 2026-05-09*
*Update after the first real application scaffold lands*

---
phase: 35
slug: replay-and-eval-hardening
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-29
updated: 2026-06-29
---

# Phase 35 — Security

Per-phase security contract for replay/eval hardening. This audit verifies the PLAN threat registers and summary threat flags for Phase 35. No new open threats were found in the summaries.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| planning artifact -> phase execution | Matrix and manifest artifacts become blocking contract inputs for later execution and verification. | Contract metadata, test paths, command strings |
| replay event registry -> matrix rows | Matrix rows may only reference registered replay events unless synchronized registry/model/migration work is planned. | Replay event identifiers and assertion metadata |
| eval command strings -> validation evidence | MOCA validation commands must use repository-scoped `uv run` or `.venv` entrypoints. | Local verification commands |
| proof projection -> authorization guard | Proof fields are inspectable evidence only and must not authorize same-merchant access in Phase 35. | Merchant proof status/source/counts |
| API caller -> trace/replay/AgentRun data | Business-data run details cross from backend to authenticated callers only through owner/admin guards. | Trace, replay, status, evidence, stream payloads |
| business fact refs -> replay projection | Scoped proof must be summarized without raw business payload leakage. | BusinessFactRef/BusinessFactResult summaries |
| persisted events -> replay API | Stored audit events become replay timeline output without rerunning model/tool/RAG/action behavior. | Redacted replay event timelines |
| operation events -> pairing validator | Operation identity links started, terminal, and retry attempts for audit interpretation. | Operation IDs, attempts, parent operation IDs |
| event payloads -> replay projection | Redacted payloads and refs cross into API-facing replay artifacts. | Redacted payloads, refs, safe summaries |
| eval manifests -> phase verification | Manifest contents become blocking evidence for deterministic Phase 35 safety gates. | Manifest schema, hashes, test refs |
| replay API -> service internals | Replay views must come from stored events, not live graph/model/tool/RAG/action execution. | Replay projections only |
| Phase 35 scope -> deferred execution/deployment work | Eval hardening must not introduce external execution, outbox/reconciliation/compensation, or physical microservice surfaces. | Static code/artifact boundaries |
| release manifest -> release claims | Release artifacts must not imply production readiness when sample size is absent. | Dataset hashes, sample gaps, metric statuses |
| monitoring manifest -> operational claims | Monitoring schema exists without claiming production telemetry has been observed. | Metric ids, status codes, schema refs |
| documentation -> future agents | Docs must point to concrete artifacts and approved commands without widening Phase 35 gates. | Artifact paths, command entrypoints |
| completed Phase 35 artifacts -> milestone closure | Validation evidence must prove coverage rather than infer success from implementation intent. | Validation reports and source audits |
| command evidence -> project state | Only MOCA-approved local entrypoints count as valid validation evidence. | Test/ruff command strings |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-35-01-01 | Tampering | `eval/replay/phase35-coverage-matrix.v1.json` | mitigate | `src/replay/phase35_matrix.py` validates required rows, gate levels, registered event names, test paths, and approved command entrypoints; covered by `tests/replay/test_phase35_coverage_matrix.py`. | closed |
| T-35-01-02 | Repudiation | coverage matrix acceptance paths | mitigate | Coverage rows require concrete pytest-backed acceptance paths and decision assertions; validated by the matrix tests and final source audit. | closed |
| T-35-01-03 | Information Disclosure | replay coverage strategy | mitigate | Matrix keeps event strategy on existing redacted event payloads and requires raw prompt/tool/PII/action payload exposure claims to have tests. | closed |
| T-35-02-01 | Elevation of Privilege | `src/api/routers/traces.py` / `src/api/routers/agent_runs.py` | mitigate | `tests/replay/test_phase35_trace_replay_permissions.py` and API regressions keep trace/replay/AgentRun visibility owner/admin-only and forbid target merchant or requested_by merchant shortcuts. | closed |
| T-35-02-02 | Information Disclosure | `src/replay/proof_projection.py` | mitigate | Proof projection emits counts/status/source/reason codes only; tests reject raw merchant/order/ticket/refund ids and raw payload strings. | closed |
| T-35-02-03 | Spoofing | replay proof status | mitigate | `BusinessFactRefV1` / `BusinessFactResultV1` proof is strictly validated and untrusted/invalid/mixed/denied/cross-merchant proof fails closed. | closed |
| T-35-03-01 | Repudiation | replay timelines | mitigate | Golden tests assert monotonic sequence, terminal/current status, and partial timeline preservation for every P0 status. | closed |
| T-35-03-02 | Tampering | operation identity | mitigate | Operation tests assert started/terminal sharing, retry parent linkage, attempt matching, and negative family/attempt/parent mismatch cases. | closed |
| T-35-03-03 | Information Disclosure | replay payload projection | mitigate | Redaction negatives cover raw prompt, raw tool payload, PII, raw action payload, secrets, credentials, API keys, unsafe debug payloads, and unsafe error fields at append/projection time. | closed |
| T-35-04-01 | Tampering | `eval/replay/dev-contract-manifest.v1.json` | mitigate | `src/replay/phase35_eval_manifest.py` validates schema, matrix hash, required categories, forbidden cases, non-blocking refs, and command entrypoints. | closed |
| T-35-04-02 | Elevation of Privilege | replay/eval forbidden behavior | mitigate | Dev-contract manifest and architecture tests include owner/admin bypass, cross-tenant/cross-merchant access, unsupported claim/action, no-evidence action, unsafe action path, stale/wrong-scope fact, invalid evidence, and approval hash mismatch cases. | closed |
| T-35-04-03 | Spoofing | replay reconstruction | mitigate | Static architecture tests forbid replay-by-rerunning graph, LLM, tool, RAG, or action services. | closed |
| T-35-05-01 | Repudiation | `eval/replay/release-gate.v1.json` | mitigate | Release manifest records dataset hash, coverage hash, command entrypoint, metric statuses, and sample gaps. | closed |
| T-35-05-02 | Tampering | `eval/replay/monitoring-gate.v1.json` | mitigate | Monitoring manifest validates exact metric ids and allowed status values through pytest. | closed |
| T-35-05-03 | Information Disclosure | release/monitoring artifacts | accept | Accepted risk: artifacts intentionally contain only aggregate metric definitions, hashes, paths, and status codes; they contain no raw prompt/tool/PII/action payloads. | closed |
| T-35-06-01 | Repudiation | `35-VALIDATION.md` | mitigate | Final validation records exact command strings, exit statuses, APF mapping, source audit rows, and no-scope checks. | closed |
| T-35-06-02 | Tampering | final scope checks | mitigate | Grep/static checks prove no real execution, replay-by-rerun, outbox/reconciliation/compensation, physical deployment, or unapproved test entrypoints were introduced. | closed |
| T-35-06-03 | Elevation of Privilege | trace/replay closure | mitigate | Final focused suite includes owner/admin visibility and cross-tenant/cross-merchant negatives from 35-02. | closed |

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-35-01 | T-35-05-03 | Release/monitoring artifacts intentionally publish aggregate metrics, hashes, paths, and status codes only. The artifact class is useful for future release/monitoring gates and does not carry raw prompt, raw tool, PII, or raw action payload data. | Codex | 2026-06-29 |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By | Evidence |
|------------|---------------|--------|------|--------|----------|
| 2026-06-29 | 18 | 18 | 0 | Codex | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_trace_replay_permissions.py tests/replay/test_phase35_redaction_negatives.py tests/eval/test_phase35_replay_eval_gates.py tests/architecture/test_phase35_replay_eval_boundaries.py -q --tb=short` -> `57 passed, 1 warning in 28.23s`; aggregate UAT command -> `122 passed, 1 warning in 40.20s`; `35-REVIEW.md` status `clean`; `35-VALIDATION.md` APF-17/APF-18 covered. |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-29

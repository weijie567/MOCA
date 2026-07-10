import { beforeEach, describe, expect, it, vi } from 'vitest'
import fixture from '@contracts/fixtures/approval_decision_context_v1.json'
import {
  apiFetch,
  getApproval,
  parseApprovalDecisionContext,
  serializeApprovalDecision,
  setAuthToken,
  setDemoUsername,
  shouldReplaceApprovalDecisionContext,
} from './api'

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 401 ? 'Unauthorized' : 'OK',
    json: async () => body,
  } as Response
}

describe('apiFetch auth refresh', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    setAuthToken(null)
    setDemoUsername(null)
  })

  it('refreshes the demo token and retries once after a protected request returns 401', async () => {
    setAuthToken('old-token')
    setDemoUsername('cs_zhang')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'UNAUTHORIZED', message: 'expired' } }))
      .mockResolvedValueOnce(jsonResponse(200, { success: true, data: { access_token: 'new-token' } }))
      .mockResolvedValueOnce(jsonResponse(200, { success: true, data: { run_id: 'run-1' } }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await apiFetch<{ run_id: string }>('/agent-runs', {
      method: 'POST',
      body: JSON.stringify({ query: 'test', thread_id: 'thread-1' }),
    })

    expect(result).toEqual({ success: true, data: { run_id: 'run-1' } })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/agent-runs')
    expect(fetchMock.mock.calls[0][1]?.headers).toMatchObject({ Authorization: 'Bearer old-token' })
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/auth/demo-token')
    expect(fetchMock.mock.calls[1][1]?.headers).not.toHaveProperty('Authorization')
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/agent-runs')
    expect(fetchMock.mock.calls[2][1]?.headers).toMatchObject({ Authorization: 'Bearer new-token' })
  })
})

describe('approval decision context v1', () => {
  it('validates the shared language-neutral fixture', () => {
    expect(parseApprovalDecisionContext(fixture)).toEqual(fixture)
  })

  it('fails closed when a binding is missing or invalid', () => {
    const { safety_snapshot_hash: _missing, ...missing } = fixture
    expect(parseApprovalDecisionContext(missing)).toBeNull()
    expect(parseApprovalDecisionContext({ ...fixture, revision: 0 })).toBeNull()
    expect(parseApprovalDecisionContext({ ...fixture, schema_version: 'approval_decision_context.v2' })).toBeNull()
  })

  it('serializes an exact frozen approve body without legacy or guessed fields', () => {
    const context = parseApprovalDecisionContext(fixture)
    expect(context).not.toBeNull()
    const body = serializeApprovalDecision(context!, { decision_type: 'approve' })
    expect(body).toEqual({
      decision_type: 'approve',
      expected_request_version: fixture.request_version,
      expected_level_version: fixture.level_version,
      expected_assignment_version: fixture.assignment_version,
      expected_revision: fixture.revision,
      action_payload_hash: fixture.action_payload_hash,
      safety_snapshot_hash: fixture.safety_snapshot_hash,
    })
    expect(body).not.toHaveProperty('decision')
  })

  it('requires reject reason and rejects unsupported decisions', () => {
    const context = parseApprovalDecisionContext(fixture)!
    expect(() => serializeApprovalDecision(context, { decision_type: 'reject', reason: '  ' })).toThrow(
      'REJECT_REASON_REQUIRED',
    )
    expect(() => serializeApprovalDecision(context, { decision_type: 'ignore' })).toThrow('UNSUPPORTED_DECISION')
  })

  it('requires immutable identity and a monotonic version advance for SSE replacement', () => {
    const current = parseApprovalDecisionContext(fixture)!
    expect(shouldReplaceApprovalDecisionContext(null, current)).toBe(true)
    expect(shouldReplaceApprovalDecisionContext(current, { ...current, request_version: current.request_version + 1 })).toBe(true)
    expect(shouldReplaceApprovalDecisionContext(current, { ...current })).toBe(false)
    expect(shouldReplaceApprovalDecisionContext(current, {
      ...current,
      revision: current.revision + 1,
      request_version: current.request_version - 1,
    })).toBe(false)

    for (const changed of [
      { tenant_ref: 'other-tenant' },
      { approval_id: '00000000-0000-0000-0000-000000000099' },
      { thread_id: 'other-thread' },
      { level_id: '00000000-0000-0000-0000-000000000098' },
      { assignment_id: '00000000-0000-0000-0000-000000000097' },
      { action_payload_hash: 'sha256:changed' },
      { safety_snapshot_ref: 'snapshot:changed' },
      { safety_snapshot_hash: 'sha256:changed' },
    ]) {
      expect(shouldReplaceApprovalDecisionContext(current, {
        ...current,
        ...changed,
        request_version: current.request_version + 1,
      })).toBe(false)
    }
  })

  it('accepts terminal approval detail with null context but rejects pending null context', async () => {
    const terminalRecord = {
      id: fixture.approval_id,
      run_id: fixture.run_id,
      status: 'approved',
      decision_context: null,
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, { success: true, data: terminalRecord }))
      .mockResolvedValueOnce(jsonResponse(200, { success: true, data: { ...terminalRecord, status: 'pending' } }))
    vi.stubGlobal('fetch', fetchMock)

    const terminal = await getApproval(fixture.approval_id)
    const pending = await getApproval(fixture.approval_id)

    expect(terminal).toEqual({ success: true, data: terminalRecord })
    expect(pending).toMatchObject({ success: false, error: { code: 'INVALID_RESPONSE' } })
  })
})

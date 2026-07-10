import { beforeEach, describe, expect, it, vi } from 'vitest'
import fixture from '@contracts/fixtures/approval_decision_context_v1.json'
import {
  apiFetch,
  parseApprovalDecisionContext,
  serializeApprovalDecision,
  setAuthToken,
  setDemoUsername,
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
})

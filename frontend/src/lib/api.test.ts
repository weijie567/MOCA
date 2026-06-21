import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, setAuthToken, setDemoUsername } from './api'

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

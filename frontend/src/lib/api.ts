const API_BASE = '/api/v1'

let authToken: string | null = null
let demoUsername: string | null = null

export type ApiResult<T> =
  | { success: true; data: T; error?: undefined }
  | { success: false; data: null; error: { code: string; message: string } }

export interface ApprovalRecord {
  id: string
  run_id: string
  status: string
  requested_by: string
  proposed_action: Record<string, unknown>
  risk_level: string
  risk_rule_ref: string | null
  risk_reason: string | null
  decision: string | null
  reason: string | null
  decided_by: string | null
  decided_at: string | null
  expires_at: string
  created_at: string
}

export function setAuthToken(token: string | null) {
  authToken = token
}

export function setDemoUsername(username: string | null) {
  demoUsername = username
}

export function getAuthToken(): string | null {
  return authToken
}

export function apiUrl(path: string) {
  return `${API_BASE}${path}`
}

async function requestDemoToken(username: string): Promise<ApiResult<{ access_token: string }>> {
  try {
    const response = await fetch(apiUrl('/auth/demo-token'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    })
    const body = await response.json().catch(() => null)

    if (!response.ok) {
      return {
        success: false,
        data: null,
        error: body?.error ?? {
          code: `HTTP_${response.status}`,
          message: response.statusText || 'Request failed',
        },
      }
    }

    if (!body || body.success !== true) {
      return {
        success: false,
        data: null,
        error: body?.error ?? { code: 'INVALID_RESPONSE', message: 'Invalid API response' },
      }
    }

    return body as ApiResult<{ access_token: string }>
  } catch (error) {
    return {
      success: false,
      data: null,
      error: {
        code: 'NETWORK_ERROR',
        message: error instanceof Error ? error.message : 'Network error',
      },
    }
  }
}

export async function refreshDemoToken() {
  if (!demoUsername) return false
  const result = await requestDemoToken(demoUsername)
  if (!result.success) return false
  setAuthToken(result.data.access_token)
  return true
}

async function fetchJson(path: string, options: RequestInit) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string> | undefined) ?? {}),
  }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`
  }
  const response = await fetch(apiUrl(path), { ...options, headers })
  const body = await response.json().catch(() => null)
  return { response, body }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> {
  try {
    let { response, body } = await fetchJson(path, options)
    if (response.status === 401 && path !== '/auth/demo-token' && (await refreshDemoToken())) {
      ;({ response, body } = await fetchJson(path, options))
    }

    if (!response.ok) {
      return {
        success: false,
        data: null,
        error: body?.error ?? {
          code: `HTTP_${response.status}`,
          message: response.statusText || 'Request failed',
        },
      }
    }

    if (!body || body.success !== true) {
      return {
        success: false,
        data: null,
        error: body?.error ?? { code: 'INVALID_RESPONSE', message: 'Invalid API response' },
      }
    }

    return body as ApiResult<T>
  } catch (error) {
    return {
      success: false,
      data: null,
      error: {
        code: 'NETWORK_ERROR',
        message: error instanceof Error ? error.message : 'Network error',
      },
    }
  }
}

export async function createRun(query: string, threadId: string) {
  return apiFetch<{ run_id: string; status: string }>('/agent-runs', {
    method: 'POST',
    body: JSON.stringify({ query, thread_id: threadId }),
  })
}

export async function getRunStatus(runId: string) {
  return apiFetch<{ run_id: string; final_status: string; final_response: string | null }>(
    `/agent-runs/${runId}`,
  )
}

export async function getRunEvidence(runId: string) {
  return apiFetch<{ evidence: Array<{ doc_key: string; title: string; confidence: number }> }>(
    `/agent-runs/${runId}/evidence`,
  )
}

export async function getRunTrace(runId: string) {
  return apiFetch<{ run_id: string; steps: Array<unknown>; timeline: Array<unknown> }>(
    `/agent-runs/${runId}/trace`,
  )
}

export async function decideApproval(
  approvalId: string,
  decision: 'approve' | 'reject',
  reason: string,
) {
  return apiFetch(`/approvals/${approvalId}/decide`, {
    method: 'POST',
    body: JSON.stringify({ decision, reason }),
  })
}

export async function getPendingApprovals() {
  return apiFetch<{ approvals: ApprovalRecord[]; total: number }>('/approvals')
}

export async function getDemoToken(username: string) {
  setDemoUsername(username)
  return requestDemoToken(username)
}

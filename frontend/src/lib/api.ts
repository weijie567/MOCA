const API_BASE = '/api/v1'

let authToken: string | null = null

export interface ApiResult<T> {
  success: boolean
  data: T
  error?: {
    code: string
    message: string
  }
}

export function setAuthToken(token: string | null) {
  authToken = token
}

export function getAuthToken(): string | null {
  return authToken
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string> | undefined) ?? {}),
  }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  return response.json() as Promise<ApiResult<T>>
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

export async function getDemoToken(username: string) {
  return apiFetch<{ access_token: string }>('/auth/demo-token', {
    method: 'POST',
    body: JSON.stringify({ username }),
  })
}

const API_BASE = '/api/v1'

let authToken: string | null = null
let demoUsername: string | null = null

export type ApiResult<T> =
  | { success: true; data: T; error?: undefined }
  | { success: false; data: null; error: { code: string; message: string } }

export type ApprovalDecisionType = 'accept' | 'approve' | 'edit' | 'respond' | 'reject' | 'ignore'

export interface ApprovalDecisionContextV1 {
  schema_version: 'approval_decision_context.v1'
  approval_id: string
  tenant_ref: string
  run_id: string
  thread_id: string
  status: string
  allowed_decision_types: ApprovalDecisionType[]
  level_id: string
  assignment_id: string
  request_version: number
  level_version: number
  assignment_version: number
  revision: number
  action_payload_hash: string
  safety_snapshot_ref: string
  safety_snapshot_hash: string
  proposed_action: Record<string, unknown>
  risk_level: string
  risk_rule_ref: string | null
  risk_reason: string | null
  expires_at: string
  created_at: string
}

export type ApprovalDecideInput =
  | { decision_type: 'accept' | 'approve' | 'ignore'; reason?: string }
  | { decision_type: 'reject'; reason: string }
  | { decision_type: 'edit'; edited_action: Record<string, unknown>; reason?: string }
  | { decision_type: 'respond'; response_text: string; reason?: string }

const DECISION_TYPES = new Set<ApprovalDecisionType>(['accept', 'approve', 'edit', 'respond', 'reject', 'ignore'])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function parseApprovalDecisionContext(value: unknown): ApprovalDecisionContextV1 | null {
  if (!isRecord(value) || value.schema_version !== 'approval_decision_context.v1') return null
  const strings = [
    'approval_id', 'tenant_ref', 'run_id', 'thread_id', 'status', 'level_id', 'assignment_id',
    'action_payload_hash', 'safety_snapshot_ref', 'safety_snapshot_hash', 'risk_level', 'expires_at', 'created_at',
  ]
  if (strings.some((key) => typeof value[key] !== 'string' || !(value[key] as string).trim())) return null
  const versions = ['request_version', 'level_version', 'assignment_version', 'revision']
  if (versions.some((key) => !Number.isInteger(value[key]) || (value[key] as number) < 1)) return null
  if (!isRecord(value.proposed_action)) return null
  if (!Array.isArray(value.allowed_decision_types) || value.allowed_decision_types.length === 0) return null
  if (!value.allowed_decision_types.every((item) => typeof item === 'string' && DECISION_TYPES.has(item as ApprovalDecisionType))) return null
  if (!(value.risk_rule_ref === null || typeof value.risk_rule_ref === 'string')) return null
  if (!(value.risk_reason === null || typeof value.risk_reason === 'string')) return null
  return value as unknown as ApprovalDecisionContextV1
}

export function serializeApprovalDecision(
  context: ApprovalDecisionContextV1,
  input: ApprovalDecideInput,
): Record<string, unknown> {
  if (!context.allowed_decision_types.includes(input.decision_type)) throw new Error('UNSUPPORTED_DECISION')
  if (input.decision_type === 'reject' && !input.reason.trim()) throw new Error('REJECT_REASON_REQUIRED')
  if (input.decision_type === 'respond' && !input.response_text.trim()) throw new Error('RESPONSE_TEXT_REQUIRED')
  const body: Record<string, unknown> = {
    decision_type: input.decision_type,
    expected_request_version: context.request_version,
    expected_level_version: context.level_version,
    expected_assignment_version: context.assignment_version,
    expected_revision: context.revision,
    action_payload_hash: context.action_payload_hash,
    safety_snapshot_hash: context.safety_snapshot_hash,
  }
  if (input.reason?.trim()) body.reason = input.reason.trim()
  if (input.decision_type === 'edit') body.edited_action = input.edited_action
  if (input.decision_type === 'respond') body.response_text = input.response_text.trim()
  return body
}

export interface ApprovalRecord {
  decision_context: ApprovalDecisionContextV1
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

export async function decideApproval(context: ApprovalDecisionContextV1, input: ApprovalDecideInput) {
  const frozen = parseApprovalDecisionContext(structuredClone(context))
  if (!frozen) throw new Error('INVALID_APPROVAL_CONTEXT')
  return apiFetch(`/approvals/${frozen.approval_id}/decide`, {
    method: 'POST',
    body: JSON.stringify(serializeApprovalDecision(frozen, input)),
  })
}

export async function getPendingApprovals() {
  const result = await apiFetch<{ approvals: ApprovalRecord[]; total: number }>('/approvals')
  if (!result.success) return result
  const approvals = result.data.approvals.flatMap((record) => {
    const context = parseApprovalDecisionContext(record.decision_context)
    return context ? [{ ...record, decision_context: context }] : []
  })
  if (approvals.length !== result.data.approvals.length) {
    return { success: false, data: null, error: { code: 'INVALID_RESPONSE', message: '审批信息不完整，请刷新后再决定。' } } as const
  }
  return { success: true, data: { approvals, total: approvals.length } } as const
}

export async function getApproval(approvalId: string) {
  const result = await apiFetch<ApprovalRecord>(`/approvals/${approvalId}`)
  if (!result.success) return result
  const context = parseApprovalDecisionContext(result.data.decision_context)
  if (!context) return { success: false, data: null, error: { code: 'INVALID_RESPONSE', message: '审批信息不完整，请刷新后再决定。' } } as const
  return { success: true, data: { ...result.data, decision_context: context } } as const
}

export async function getDemoToken(username: string) {
  setDemoUsername(username)
  return requestDemoToken(username)
}

export type RunStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'insufficient_evidence'
  | 'waiting_approval'
  | 'interrupted'
  | 'rejected'
  | 'degraded'
  | 'failed'
  | 'error'
  | 'manual_review'
  | 'refused'
  | 'disconnected'

export type SseEventType =
  | 'run_started'
  | 'step_started'
  | 'step_completed'
  | 'final_response'
  | 'approval_required'
  | 'error'

export type BusinessQueryOperation = 'aggregate' | 'list' | 'detail' | 'breakdown' | 'compare'

export type BusinessQueryRowValue = string | number | boolean | null

export type BusinessQueryRow = Record<string, BusinessQueryRowValue>

export interface BusinessQueryPayload {
  operation: BusinessQueryOperation
  resource_label?: string
  result_label?: string
  scope_label?: string
  time_label?: string
  filters_label?: string
  freshness_label?: string
  fields_label?: string
  safe_reason?: string
  rows?: BusinessQueryRow[]
  row_count?: number
  limit?: number
  cursor_label?: string
  allowed_drilldowns?: string[]
  group_by_label?: string
  compare_label?: string
}

export interface SseEventPayload {
  evidence_count?: number
  tool_name?: string
  tool_label?: string
  risk_level?: string
  short_summary?: string
  approval_id?: string
  decision_context?: ApprovalDecisionContextV1
  proposed_action?: Record<string, unknown>
  final_response?: string
  response_kind?:
    | 'small_talk'
    | 'direct_response'
    | 'clarification'
    | 'unsupported'
    | 'metric_answer'
    | 'business_query_answer'
    | 'rag_answer'
    | string
  safe_reason?: string
  business_query?: BusinessQueryPayload
  metric_id?: string
  metric_label?: string
  scope_label?: string
  time_label?: string
  filters_label?: string
  freshness_label?: string
  metric?: {
    metric_id?: string
    metric_label?: string
    scope_label?: string
    time_label?: string
    filters_label?: string
    freshness_label?: string
    safe_reason?: string
  }
  error_code?: string
  error_message?: string
  final_status?: string
}

export interface SseEvent {
  event_type: SseEventType
  run_id: string
  step_index: number
  node_name: string | null
  status: RunStatus
  message: string
  timestamp: string
  payload?: SseEventPayload
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: 'completed' | 'pending' | 'error'
  runId?: string
}
import type { ApprovalDecisionContextV1 } from '@/lib/api'

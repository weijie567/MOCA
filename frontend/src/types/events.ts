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
  | 'disconnected'

export type SseEventType =
  | 'run_started'
  | 'step_started'
  | 'step_completed'
  | 'final_response'
  | 'approval_required'
  | 'error'

export interface SseEventPayload {
  evidence_count?: number
  tool_name?: string
  tool_label?: string
  risk_level?: string
  short_summary?: string
  approval_id?: string
  proposed_action?: Record<string, unknown>
  final_response?: string
  response_kind?:
    | 'small_talk'
    | 'direct_response'
    | 'clarification'
    | 'unsupported'
    | 'metric_answer'
    | 'rag_answer'
    | string
  safe_reason?: string
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

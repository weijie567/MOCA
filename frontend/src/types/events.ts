export type RunStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'waiting_approval'
  | 'interrupted'
  | 'rejected'
  | 'degraded'
  | 'failed'
  | 'error'
  | 'disconnected'

export type SseEventType =
  | 'run_started'
  | 'node_started'
  | 'node_completed'
  | 'tool_called'
  | 'evidence_retrieved'
  | 'approval_required'
  | 'final_response'
  | 'run_completed'
  | 'run_failed'

export interface SseEventPayload {
  evidence_count?: number
  tool_name?: string
  risk_level?: string
  short_summary?: string
  approval_id?: string
  proposed_action?: Record<string, unknown>
  final_response?: string
  error_code?: string
  error_message?: string
}

export interface SseEvent {
  event_type: SseEventType
  run_id: string
  step_index: number
  node_name: string
  status: RunStatus
  message: string
  timestamp: string
  payload?: SseEventPayload
}

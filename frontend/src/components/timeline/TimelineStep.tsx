import { AlertCircle, CheckCircle2, Clock3, PauseCircle } from 'lucide-react'
import type { SseEvent } from '@/types/events'
import { cn } from '@/lib/utils'

const NODE_MESSAGES: Record<string, string> = {
  receive_request: '正在接收请求',
  safety_pre_route: '正在进行安全预路由',
  session_context_load: '正在加载会话上下文',
  contextual_intent_resolve: '正在识别上下文意图',
  slot_resolution_gate: '正在确认关键信息',
  memory_context_load: '正在加载记忆上下文',
  investigate: '正在调查订单和规则',
  rag_context_build: '正在构建证据上下文',
  recommendation_generation: '正在生成处理建议',
  claim_verify: '正在校验建议依据',
  risk_gate: '正在评估风险',
  approval_gate: '需要审批，等待人工决策',
  action_draft: '正在生成操作草稿',
  clarification_gate: '需要补充信息',
  final_response: '已完成',
}

const STATUS_DOT: Record<string, string> = {
  pending: 'bg-status-disconnected',
  running: 'bg-status-running',
  completed: 'bg-status-completed',
  waiting_approval: 'bg-status-waiting',
  interrupted: 'bg-status-waiting',
  rejected: 'bg-status-rejected',
  degraded: 'bg-status-degraded',
  failed: 'bg-status-failed',
  error: 'bg-status-failed',
  disconnected: 'bg-status-disconnected',
}

const SAFE_REASON_LABELS: Record<string, string> = {
  aggregate_order_query: '缺少时间范围',
  approval_chat_not_trusted: '审批需要通过审批入口',
  low_confidence: '需要更多业务背景',
  merchant_filter: '缺少商家范围',
  metric_scope_denied: '当前权限范围无法提供',
  metric_status_filter: '状态筛选不适用',
  missing_case_identifier: '缺少业务标识',
  missing_identifier: '缺少业务标识',
  missing_order_reference: '缺少业务标识',
  missing_required_slots: '缺少必要信息',
  missing_time_range: '缺少时间范围',
  multi_target_request: '存在多个处理目标',
  scope_denied_no_existence_leak: '当前权限范围无法提供',
  unsupported_metric: '不支持的统计口径',
  unsupported_or_ambiguous: '暂不在可直接处理范围',
}

const TOOL_LABELS: Record<string, string> = {
  create_coupon_grant_draft: '生成补偿券草稿',
  get_order: '查询订单',
  get_refund_case: '查询退款单',
  get_ticket: '查询工单',
  query_business_metric: '查询业务指标',
  search_policy: '检索政策证据',
}

function formatTime(timestamp: string) {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return timestamp
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle2 className="h-3.5 w-3.5 text-status-completed" />
  if (status === 'waiting_approval' || status === 'interrupted') {
    return <PauseCircle className="h-3.5 w-3.5 text-status-waiting" />
  }
  if (status === 'failed' || status === 'error' || status === 'rejected') {
    return <AlertCircle className="h-3.5 w-3.5 text-status-failed" />
  }
  return <Clock3 className="h-3.5 w-3.5 text-muted-foreground" />
}

function safeText(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

function safeReasonLabel(value: unknown) {
  const reason = safeText(value)
  if (!reason) return ''
  return SAFE_REASON_LABELS[reason] ?? '已安全处理'
}

function responseKind(step: SseEvent) {
  return safeText(step.payload?.response_kind)
}

function metricPayload(step: SseEvent) {
  return {
    metric_id: safeText(step.payload?.metric?.metric_id || step.payload?.metric_id),
    metric_label: safeText(step.payload?.metric?.metric_label || step.payload?.metric_label),
    scope_label: safeText(step.payload?.metric?.scope_label || step.payload?.scope_label),
  }
}

function metricSubtitle(step: SseEvent) {
  const metric = metricPayload(step)
  const metricLabel = metric.metric_label || metric.metric_id || 'business_metric'
  const scopeLabel = metric.scope_label || '当前权限范围'
  return `metric: ${metricLabel} · scope: ${scopeLabel}`
}

function toolLabel(step: SseEvent) {
  const explicit = safeText(step.payload?.tool_label)
  if (explicit) return explicit
  const toolName = safeText(step.payload?.tool_name)
  return TOOL_LABELS[toolName] ?? ''
}

function timelineLabel(step: SseEvent) {
  const kind = responseKind(step)
  const nodeName = step.node_name ?? ''
  const tool = toolLabel(step)

  if (kind === 'metric_answer' || step.payload?.metric || step.payload?.metric_id) {
    return step.status === 'running' ? '正在查询业务指标' : '业务指标查询完成'
  }
  if (kind === 'small_talk' || kind === 'direct_response') return '直接回复'
  if (kind === 'clarification') return '需要补充信息'
  if (kind === 'unsupported') return '当前能力不支持'
  if (kind === 'rag_answer' || nodeName === 'rag_context_build') return NODE_MESSAGES.rag_context_build
  if (tool) return tool
  return step.message || (nodeName ? NODE_MESSAGES[nodeName] : '') || `正在执行 ${step.event_type}`
}

function timelineSubtitle(step: SseEvent) {
  const kind = responseKind(step)
  const nodeName = step.node_name ?? ''
  const tool = toolLabel(step)

  if (kind === 'metric_answer' || step.payload?.metric || step.payload?.metric_id) {
    return metricSubtitle(step)
  }
  if (kind === 'small_talk' || kind === 'direct_response') return 'response: direct'
  if (kind === 'clarification' || kind === 'unsupported') {
    const reason = safeReasonLabel(step.payload?.safe_reason)
    return reason ? `原因: ${reason}` : '原因: 已安全处理'
  }
  if ((kind === 'rag_answer' || nodeName === 'rag_context_build') && typeof step.payload?.evidence_count === 'number') {
    return `evidence: ${step.payload.evidence_count}`
  }
  if (tool) return `tool: ${tool}`
  return `${nodeName || step.event_type} · status: ${step.status}`
}

interface TimelineStepProps {
  step: SseEvent
  isLast: boolean
}

export function TimelineStep({ step, isLast }: TimelineStepProps) {
  const message = timelineLabel(step)
  const subtitle = timelineSubtitle(step)
  const dotClass = STATUS_DOT[step.status] ?? STATUS_DOT.pending

  return (
    <li className="relative grid grid-cols-[20px_1fr_auto] gap-3 pb-4">
      {!isLast ? (
        <span className="absolute left-[9px] top-5 h-[calc(100%-20px)] border-l border-border" aria-hidden="true" />
      ) : null}
      <span
        className={cn(
          'relative z-10 mt-1 h-2 w-2 rounded-full ring-4 ring-background',
          dotClass,
          step.status === 'running' ? 'animate-pulse' : '',
        )}
        aria-label={step.status}
      />
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <StatusIcon status={step.status} />
          <p className="truncate text-body font-semibold">{message}</p>
        </div>
        <p className="mt-1 truncate text-label text-muted-foreground">{subtitle}</p>
      </div>
      <time className="pt-0.5 text-label text-muted-foreground">{formatTime(step.timestamp)}</time>
    </li>
  )
}

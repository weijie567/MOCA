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

interface TimelineStepProps {
  step: SseEvent
  isLast: boolean
}

export function TimelineStep({ step, isLast }: TimelineStepProps) {
  const nodeName = step.node_name ?? ''
  const message = step.message || (nodeName ? NODE_MESSAGES[nodeName] : '') || `正在执行 ${step.event_type}`
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
        <p className="mt-1 truncate text-label text-muted-foreground">
          {nodeName || step.event_type} · status: {step.status}
        </p>
      </div>
      <time className="pt-0.5 text-label text-muted-foreground">{formatTime(step.timestamp)}</time>
    </li>
  )
}

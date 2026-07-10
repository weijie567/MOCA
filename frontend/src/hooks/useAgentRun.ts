import { useCallback, useEffect, useRef, useState } from 'react'
import { createRun, decideApproval, getApproval, getRunStatus, parseApprovalDecisionContext } from '@/lib/api'
import type { ApprovalDecisionContextV1 } from '@/lib/api'
import { connectToRunEvents } from '@/lib/sse'
import type { ChatMessage, RunStatus, SseEvent } from '@/types/events'

type AgentRunStatus = RunStatus | 'idle'

interface AgentRunState {
  runId: string | null
  status: AgentRunStatus
  steps: SseEvent[]
  messages: ChatMessage[]
  finalResponse: string | null
  approvalId: string | null
  approvalContext: ApprovalDecisionContextV1 | null
  approvalContextFresh: boolean
  activeAssistantMessageId: string | null
  error: string | null
}

const INITIAL_STATE: AgentRunState = {
  runId: null,
  status: 'idle',
  steps: [],
  messages: [],
  finalResponse: null,
  approvalId: null,
  approvalContext: null,
  approvalContextFresh: false,
  activeAssistantMessageId: null,
  error: null,
}

const THREAD_ID_STORAGE_KEY = 'moca.agent.threadId'
const DEFAULT_ERROR_MESSAGE = '执行遇到问题，请重试。如问题持续，请联系管理员'
let messageCounter = 0

const TERMINAL_STATUSES = new Set<AgentRunStatus>([
  'completed',
  'insufficient_evidence',
  'rejected',
  'degraded',
  'failed',
  'error',
])

function normalizeStatus(status: string | null | undefined): AgentRunStatus {
  if (!status) return 'running'
  if (status === 'interrupted') return 'waiting_approval'
  if (status === 'error') return 'failed'
  return status as AgentRunStatus
}

function createThreadId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `demo-${crypto.randomUUID()}`
  }
  return `demo-${Date.now()}`
}

function createMessageId(role: ChatMessage['role']) {
  messageCounter += 1
  return `${role}-${Date.now()}-${messageCounter}`
}

function readStoredThreadId() {
  if (typeof window === 'undefined') return null

  try {
    return window.localStorage.getItem(THREAD_ID_STORAGE_KEY)
  } catch {
    return null
  }
}

function storeThreadId(threadId: string) {
  if (typeof window === 'undefined') return

  try {
    window.localStorage.setItem(THREAD_ID_STORAGE_KEY, threadId)
  } catch {
    // Conversation continuity is best-effort when storage is unavailable.
  }
}

function getInitialThreadId() {
  const storedThreadId = readStoredThreadId()
  if (storedThreadId) return storedThreadId

  const threadId = createThreadId()
  storeThreadId(threadId)
  return threadId
}

function nextStepIndex(steps: SseEvent[]) {
  return steps.reduce((max, step) => Math.max(max, step.step_index), 0) + 1
}

function timelineEventKey(event: SseEvent) {
  if (event.event_type === 'run_started') return 'receive_request'
  if (event.event_type === 'final_response' || event.node_name === 'final_response') return 'final_response'
  if (event.event_type === 'approval_required' || event.node_name === 'approval_gate') return 'approval_gate'
  if (event.event_type === 'error') return 'error'
  return event.node_name || `${event.event_type}-${event.step_index}`
}

function upsertTimelineEvent(steps: SseEvent[], event: SseEvent) {
  const key = timelineEventKey(event)
  const existingIndex = steps.findIndex((step) => timelineEventKey(step) === key)
  if (existingIndex === -1) return [...steps, event]

  return steps.map((step, index) => {
    if (index !== existingIndex) return step
    return {
      ...step,
      ...event,
      node_name: event.node_name ?? step.node_name,
      payload: {
        ...(step.payload ?? {}),
        ...(event.payload ?? {}),
      },
    }
  })
}

function runStatusFromEvent(currentStatus: AgentRunStatus, event: SseEvent): AgentRunStatus {
  if (event.event_type === 'approval_required' || event.status === 'waiting_approval' || event.status === 'interrupted') {
    return 'waiting_approval'
  }
  if (event.event_type === 'error' || event.status === 'failed' || event.status === 'error') {
    return 'failed'
  }
  if (event.event_type === 'final_response') {
    return 'completed'
  }
  if (event.event_type === 'run_started' || event.event_type === 'step_started' || event.event_type === 'step_completed') {
    return currentStatus === 'waiting_approval' ? currentStatus : 'running'
  }
  return normalizeStatus(event.status)
}

function updateAssistantMessage(
  messages: ChatMessage[],
  messageId: string | null,
  patch: Partial<Pick<ChatMessage, 'content' | 'status' | 'runId'>>,
) {
  if (!messageId) return messages
  return messages.map((message) => (message.id === messageId ? { ...message, ...patch } : message))
}

function withRecoveredTerminalStep(
  steps: SseEvent[],
  runId: string,
  status: AgentRunStatus,
  finalResponse: string | null,
  errorMessage: string | null,
) {
  if (steps.some((step) => step.event_type === 'final_response' || step.event_type === 'error')) {
    return steps
  }

  if (status === 'completed' && finalResponse) {
    return upsertTimelineEvent(steps, {
      event_type: 'final_response',
      run_id: runId,
      step_index: nextStepIndex(steps),
      node_name: 'final_response',
      status: 'completed',
      message: '已完成',
      timestamp: new Date().toISOString(),
      payload: { final_response: finalResponse },
    })
  }

  if (status === 'failed' || status === 'error') {
    return upsertTimelineEvent(steps, {
      event_type: 'error',
      run_id: runId,
      step_index: nextStepIndex(steps),
      node_name: 'error',
      status: 'failed',
      message: '执行遇到问题，请重试',
      timestamp: new Date().toISOString(),
      payload: { error_message: errorMessage ?? DEFAULT_ERROR_MESSAGE },
    })
  }

  return steps
}

export function useAgentRun() {
  const [state, setState] = useState<AgentRunState>(INITIAL_STATE)
  const [threadId, setThreadId] = useState(() => getInitialThreadId())
  const controllerRef = useRef<AbortController | null>(null)
  const pollTimerRef = useRef<number | null>(null)
  const closeExpectedRef = useRef(false)
  const runGenerationRef = useRef(0)

  const clearPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const stopStream = useCallback(() => {
    closeExpectedRef.current = true
    controllerRef.current?.abort()
    controllerRef.current = null
  }, [])

  const recoverRunStatus = useCallback(async (runId: string, expectedGeneration = runGenerationRef.current) => {
    try {
      const result = await getRunStatus(runId)
      if (expectedGeneration !== runGenerationRef.current) return
      if (!result.success) {
        setState((current) => ({
          ...current,
          status: 'failed',
          error: result.error?.message ?? '无法恢复执行状态',
        }))
        return
      }

      const recoveredStatus = normalizeStatus(result.data.final_status)
      const finalResponse = result.data.final_response ?? null
      setState((current) => {
        if (current.runId && current.runId !== runId) return current
        return {
          ...current,
          status: recoveredStatus,
          steps: withRecoveredTerminalStep(
            current.steps,
            runId,
            recoveredStatus,
            finalResponse ?? current.finalResponse,
            null,
          ),
          messages: finalResponse
            ? updateAssistantMessage(current.messages, current.activeAssistantMessageId, {
                content: finalResponse,
                status: 'completed',
                runId,
              })
            : recoveredStatus === 'failed'
              ? updateAssistantMessage(current.messages, current.activeAssistantMessageId, {
                  content: DEFAULT_ERROR_MESSAGE,
                  status: 'error',
                  runId,
                })
              : current.messages,
          finalResponse: finalResponse ?? current.finalResponse,
          activeAssistantMessageId: TERMINAL_STATUSES.has(recoveredStatus) ? null : current.activeAssistantMessageId,
          error: recoveredStatus === 'failed' ? DEFAULT_ERROR_MESSAGE : null,
        }
      })
    } catch {
      if (expectedGeneration !== runGenerationRef.current) return
      setState((current) => ({
        ...current,
        status: 'failed',
        error: '连接中断，状态恢复失败',
      }))
    }
  }, [])

  const startPolling = useCallback(
    (runId: string) => {
      clearPolling()
      const generation = runGenerationRef.current
      pollTimerRef.current = window.setInterval(() => {
        void (async () => {
          try {
            const result = await getRunStatus(runId)
            if (generation !== runGenerationRef.current) {
              clearPolling()
              return
            }
            if (!result.success) {
              setState((current) => ({
                ...current,
                status: 'failed',
                error: result.error?.message ?? '无法获取审批后的执行状态',
              }))
              clearPolling()
              return
            }

            const nextStatus = normalizeStatus(result.data.final_status)
            const finalResponse = result.data.final_response ?? null
            setState((current) => {
              if (current.runId && current.runId !== runId) return current
              return {
                ...current,
                status: nextStatus,
                steps: withRecoveredTerminalStep(
                  current.steps,
                  runId,
                  nextStatus,
                  finalResponse ?? current.finalResponse,
                  null,
                ),
                messages: finalResponse
                  ? updateAssistantMessage(current.messages, current.activeAssistantMessageId, {
                      content: finalResponse,
                      status: 'completed',
                      runId,
                    })
                  : nextStatus === 'failed'
                    ? updateAssistantMessage(current.messages, current.activeAssistantMessageId, {
                        content: DEFAULT_ERROR_MESSAGE,
                        status: 'error',
                        runId,
                      })
                    : current.messages,
                finalResponse: finalResponse ?? current.finalResponse,
                activeAssistantMessageId:
                  TERMINAL_STATUSES.has(nextStatus) && nextStatus !== 'waiting_approval'
                    ? null
                    : current.activeAssistantMessageId,
                error: nextStatus === 'failed' ? DEFAULT_ERROR_MESSAGE : null,
              }
            })

            if (TERMINAL_STATUSES.has(nextStatus)) {
              clearPolling()
            }
          } catch {
            if (generation !== runGenerationRef.current) return
            setState((current) => ({
              ...current,
              status: 'failed',
              error: '连接中断，状态恢复失败',
            }))
            clearPolling()
          }
        })()
      }, 2000)
    },
    [clearPolling],
  )

  const attachStream = useCallback(
    (runId: string, assistantMessageId: string, generation: number) => {
      closeExpectedRef.current = false
      controllerRef.current = connectToRunEvents(runId, {
        onEvent(event) {
          if (generation !== runGenerationRef.current) return
          setState((current) => {
            if (current.runId && current.runId !== runId) {
              return current
            }
            const nextStatus = runStatusFromEvent(current.status, event)
            const approvalId = event.payload?.approval_id ?? current.approvalId
            const incomingContext = parseApprovalDecisionContext(event.payload?.decision_context)
            const approvalContext = incomingContext && incomingContext.run_id === runId
              ? incomingContext
              : current.approvalContext
            const finalResponse = event.payload?.final_response ?? current.finalResponse
            const errorMessage = event.payload?.error_message ?? current.error ?? DEFAULT_ERROR_MESSAGE

            if (event.event_type === 'approval_required' || nextStatus === 'waiting_approval') {
              closeExpectedRef.current = true
            }
            if (event.event_type === 'final_response' || TERMINAL_STATUSES.has(nextStatus)) {
              closeExpectedRef.current = true
            }

            const messages = event.payload?.final_response
              ? updateAssistantMessage(current.messages, assistantMessageId, {
                  content: event.payload.final_response,
                  status: 'completed',
                  runId,
                })
              : nextStatus === 'failed'
                ? updateAssistantMessage(current.messages, assistantMessageId, {
                    content: errorMessage,
                    status: 'error',
                    runId,
                  })
                : current.messages

            return {
              ...current,
              status: nextStatus,
              steps: upsertTimelineEvent(current.steps, event),
              messages,
              approvalId,
              approvalContext,
              approvalContextFresh: incomingContext?.run_id === runId,
              finalResponse,
              activeAssistantMessageId:
                event.event_type === 'final_response' || nextStatus === 'failed'
                  ? null
                  : current.activeAssistantMessageId,
              error: nextStatus === 'failed' ? errorMessage : null,
            }
          })
        },
        onError(error) {
          if (generation !== runGenerationRef.current) return
          if (closeExpectedRef.current) return
          setState((current) => ({ ...current, status: 'disconnected', approvalContextFresh: false, error: error.message }))
          void recoverRunStatus(runId, generation)
        },
        onClose() {
          if (generation !== runGenerationRef.current) return
          if (closeExpectedRef.current) return
          setState((current) => ({ ...current, status: 'disconnected', approvalContextFresh: false }))
          void recoverRunStatus(runId, generation)
        },
      })
    },
    [recoverRunStatus],
  )

  const submitQuery = useCallback(
    async (query: string) => {
      const trimmedQuery = query.trim()
      if (!trimmedQuery) return

      runGenerationRef.current += 1
      const generation = runGenerationRef.current
      stopStream()
      clearPolling()
      const userMessage: ChatMessage = {
        id: createMessageId('user'),
        role: 'user',
        content: trimmedQuery,
        status: 'completed',
      }
      const assistantMessage: ChatMessage = {
        id: createMessageId('assistant'),
        role: 'assistant',
        content: '',
        status: 'pending',
      }

      setState((current) => ({
        ...INITIAL_STATE,
        messages: [...current.messages, userMessage, assistantMessage],
        activeAssistantMessageId: assistantMessage.id,
        status: 'running',
      }))

      try {
        const result = await createRun(trimmedQuery, threadId)
        if (generation !== runGenerationRef.current) return
        if (!result.success) {
          setState((current) => ({
            ...current,
            status: 'failed',
            messages: updateAssistantMessage(current.messages, assistantMessage.id, {
              content: result.error?.message ?? DEFAULT_ERROR_MESSAGE,
              status: 'error',
            }),
            activeAssistantMessageId: null,
            error: result.error?.message ?? DEFAULT_ERROR_MESSAGE,
          }))
          return
        }

        setState((current) => ({
          ...current,
          runId: result.data.run_id,
          status: normalizeStatus(result.data.status),
          messages: updateAssistantMessage(current.messages, assistantMessage.id, {
            runId: result.data.run_id,
          }),
        }))
        attachStream(result.data.run_id, assistantMessage.id, generation)
      } catch {
        if (generation !== runGenerationRef.current) return
        setState((current) => ({
          ...current,
          status: 'failed',
          messages: updateAssistantMessage(current.messages, assistantMessage.id, {
            content: DEFAULT_ERROR_MESSAGE,
            status: 'error',
          }),
          activeAssistantMessageId: null,
          error: DEFAULT_ERROR_MESSAGE,
        }))
      }
    },
    [attachStream, clearPolling, stopStream, threadId],
  )

  const approveRun = useCallback(async () => {
    if (!state.approvalContext || !state.approvalContextFresh || !state.runId) return
    try {
      const latest = await getApproval(state.approvalContext.approval_id)
      if (!latest.success) {
        setState((current) => ({ ...current, approvalContextFresh: false, error: latest.error.message }))
        return
      }
      const frozen = latest.data.decision_context
      const result = await decideApproval(frozen, { decision_type: 'approve' })
      if (!result.success) {
        await getApproval(frozen.approval_id)
        setState((current) => ({
          ...current,
          approvalContextFresh: false,
          error: result.error?.message ?? '审批提交失败',
        }))
        return
      }
      setState((current) => ({ ...current, status: 'running', error: null }))
      startPolling(state.runId)
    } catch {
      if (state.approvalContext) await getApproval(state.approvalContext.approval_id)
      setState((current) => ({
        ...current,
        approvalContextFresh: false,
        error: '提交结果未确认，正在查询最新状态。请勿重复提交。',
      }))
    }
  }, [startPolling, state.approvalContext, state.approvalContextFresh, state.runId])

  const rejectRun = useCallback(
    async (reason: string) => {
      if (!state.approvalContext || !state.approvalContextFresh || !state.runId || !reason.trim()) return
      try {
        const latest = await getApproval(state.approvalContext.approval_id)
        if (!latest.success) {
          setState((current) => ({ ...current, approvalContextFresh: false, error: latest.error.message }))
          return
        }
        const frozen = latest.data.decision_context
        const result = await decideApproval(frozen, { decision_type: 'reject', reason })
        if (!result.success) {
          await getApproval(frozen.approval_id)
          setState((current) => ({
            ...current,
            approvalContextFresh: false,
            error: result.error?.message ?? '审批提交失败',
          }))
          return
        }
        setState((current) => ({
          ...current,
          status: 'rejected',
          messages: updateAssistantMessage(current.messages, current.activeAssistantMessageId, {
            content: `审批已拒绝：${reason}`,
            status: 'error',
          }),
          activeAssistantMessageId: null,
          error: reason,
        }))
        startPolling(state.runId)
      } catch {
        if (state.approvalContext) await getApproval(state.approvalContext.approval_id)
        setState((current) => ({
          ...current,
          approvalContextFresh: false,
          error: '提交结果未确认，正在查询最新状态。请勿重复提交。',
        }))
      }
    },
    [startPolling, state.approvalContext, state.approvalContextFresh, state.runId],
  )

  const reset = useCallback(() => {
    runGenerationRef.current += 1
    stopStream()
    clearPolling()
    setState(INITIAL_STATE)
  }, [clearPolling, stopStream])

  const newConversation = useCallback(() => {
    reset()
    const nextThreadId = createThreadId()
    storeThreadId(nextThreadId)
    setThreadId(nextThreadId)
  }, [reset])

  useEffect(() => {
    return () => {
      stopStream()
      clearPolling()
    }
  }, [clearPolling, stopStream])

  return {
    state,
    submitQuery,
    approveRun,
    rejectRun,
    reset,
    newConversation,
    resetConversation: newConversation,
  }
}

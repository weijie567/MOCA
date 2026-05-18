import { useCallback, useEffect, useRef, useState } from 'react'
import { createRun, decideApproval, getRunStatus } from '@/lib/api'
import { connectToRunEvents } from '@/lib/sse'
import type { RunStatus, SseEvent } from '@/types/events'

type AgentRunStatus = RunStatus | 'idle'

interface AgentRunState {
  runId: string | null
  status: AgentRunStatus
  steps: SseEvent[]
  finalResponse: string | null
  approvalId: string | null
  error: string | null
}

const INITIAL_STATE: AgentRunState = {
  runId: null,
  status: 'idle',
  steps: [],
  finalResponse: null,
  approvalId: null,
  error: null,
}

const TERMINAL_STATUSES = new Set<AgentRunStatus>([
  'completed',
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

function nextStepIndex(steps: SseEvent[]) {
  return steps.reduce((max, step) => Math.max(max, step.step_index), 0) + 1
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
    return [
      ...steps,
      {
        event_type: 'final_response',
        run_id: runId,
        step_index: nextStepIndex(steps),
        node_name: 'final_response',
        status: 'completed',
        message: '已完成',
        timestamp: new Date().toISOString(),
        payload: { final_response: finalResponse },
      } satisfies SseEvent,
    ]
  }

  if (status === 'failed' || status === 'error') {
    return [
      ...steps,
      {
        event_type: 'error',
        run_id: runId,
        step_index: nextStepIndex(steps),
        node_name: 'error',
        status: 'failed',
        message: '执行遇到问题，请重试',
        timestamp: new Date().toISOString(),
        payload: { error_message: errorMessage ?? '执行遇到问题，请重试。如问题持续，请联系管理员' },
      } satisfies SseEvent,
    ]
  }

  return steps
}

export function useAgentRun() {
  const [state, setState] = useState<AgentRunState>(INITIAL_STATE)
  const controllerRef = useRef<AbortController | null>(null)
  const pollTimerRef = useRef<number | null>(null)
  const closeExpectedRef = useRef(false)

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

  const recoverRunStatus = useCallback(async (runId: string) => {
    try {
      const result = await getRunStatus(runId)
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
      setState((current) => ({
        ...current,
        status: recoveredStatus,
        steps: withRecoveredTerminalStep(
          current.steps,
          runId,
          recoveredStatus,
          finalResponse ?? current.finalResponse,
          null,
        ),
        finalResponse: finalResponse ?? current.finalResponse,
        error: recoveredStatus === 'failed' ? '执行遇到问题，请重试。如问题持续，请联系管理员' : null,
      }))
    } catch {
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
      pollTimerRef.current = window.setInterval(() => {
        void (async () => {
          try {
            const result = await getRunStatus(runId)
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
            setState((current) => ({
              ...current,
              status: nextStatus,
              steps: withRecoveredTerminalStep(
                current.steps,
                runId,
                nextStatus,
                finalResponse ?? current.finalResponse,
                null,
              ),
              finalResponse: finalResponse ?? current.finalResponse,
              error: nextStatus === 'failed' ? '执行遇到问题，请重试。如问题持续，请联系管理员' : null,
            }))

            if (TERMINAL_STATUSES.has(nextStatus)) {
              clearPolling()
            }
          } catch {
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
    (runId: string) => {
      closeExpectedRef.current = false
      controllerRef.current = connectToRunEvents(runId, {
        onEvent(event) {
          setState((current) => {
            const nextStatus = normalizeStatus(event.status)
            const approvalId = event.payload?.approval_id ?? current.approvalId
            const finalResponse = event.payload?.final_response ?? current.finalResponse
            const errorMessage = event.payload?.error_message ?? current.error

            if (event.event_type === 'approval_required' || nextStatus === 'waiting_approval') {
              closeExpectedRef.current = true
            }
            if (event.event_type === 'final_response' || TERMINAL_STATUSES.has(nextStatus)) {
              closeExpectedRef.current = true
            }

            return {
              ...current,
              status: nextStatus,
              steps: [...current.steps, event],
              approvalId,
              finalResponse,
              error: nextStatus === 'failed' ? errorMessage ?? '执行遇到问题，请重试。如问题持续，请联系管理员' : null,
            }
          })
        },
        onError(error) {
          if (closeExpectedRef.current) return
          setState((current) => ({ ...current, status: 'disconnected', error: error.message }))
          void recoverRunStatus(runId)
        },
        onClose() {
          if (closeExpectedRef.current) return
          setState((current) => ({ ...current, status: 'disconnected' }))
          void recoverRunStatus(runId)
        },
      })
    },
    [recoverRunStatus],
  )

  const submitQuery = useCallback(
    async (query: string) => {
      const trimmedQuery = query.trim()
      if (!trimmedQuery) return

      stopStream()
      clearPolling()

      setState({
        ...INITIAL_STATE,
        status: 'running',
      })

      try {
        const result = await createRun(trimmedQuery, createThreadId())
        if (!result.success) {
          setState((current) => ({
            ...current,
            status: 'failed',
            error: result.error?.message ?? '执行遇到问题，请重试。如问题持续，请联系管理员',
          }))
          return
        }

        setState((current) => ({
          ...current,
          runId: result.data.run_id,
          status: normalizeStatus(result.data.status),
        }))
        attachStream(result.data.run_id)
      } catch {
        setState((current) => ({
          ...current,
          status: 'failed',
          error: '执行遇到问题，请重试。如问题持续，请联系管理员',
        }))
      }
    },
    [attachStream, clearPolling, stopStream],
  )

  const approveRun = useCallback(async () => {
    if (!state.approvalId || !state.runId) return
    try {
      const result = await decideApproval(state.approvalId, 'approve', 'Approved from MOCA demo console')
      if (!result.success) {
        setState((current) => ({
          ...current,
          status: 'failed',
          error: result.error?.message ?? '审批提交失败',
        }))
        return
      }
      setState((current) => ({ ...current, status: 'running', error: null }))
      startPolling(state.runId)
    } catch {
      setState((current) => ({
        ...current,
        status: 'failed',
        error: '审批提交失败',
      }))
    }
  }, [startPolling, state.approvalId, state.runId])

  const rejectRun = useCallback(
    async (reason: string) => {
      if (!state.approvalId || !state.runId) return
      try {
        const result = await decideApproval(state.approvalId, 'reject', reason)
        if (!result.success) {
          setState((current) => ({
            ...current,
            status: 'failed',
            error: result.error?.message ?? '审批提交失败',
          }))
          return
        }
        setState((current) => ({ ...current, status: 'rejected', error: reason }))
        startPolling(state.runId)
      } catch {
        setState((current) => ({
          ...current,
          status: 'failed',
          error: '审批提交失败',
        }))
      }
    },
    [startPolling, state.approvalId, state.runId],
  )

  const reset = useCallback(() => {
    stopStream()
    clearPolling()
    setState(INITIAL_STATE)
  }, [clearPolling, stopStream])

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
  }
}

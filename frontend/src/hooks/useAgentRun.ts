import { useCallback, useEffect, useRef, useState } from 'react'
import {
  createRun,
  freezeApprovalSubmission,
  getApproval,
  getRunStatus,
  isExactApprovalDecisionContext,
  isTerminalApprovalStatus,
  parseApprovalDecisionContext,
  shouldReplaceApprovalDecisionContext,
  submitFrozenApprovalSubmission,
} from '@/lib/api'
import type {
  ApprovalDecisionContextV1,
  ApprovalRecord,
  ApprovalSubmissionOutcome,
  FrozenApprovalSubmission,
} from '@/lib/api'
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
const RESUME_INCOMPLETE_MESSAGE = '审批决定已保存，但运行恢复尚未完成。请确认后重试恢复；系统不会自动重复提交审批决定。'
let messageCounter = 0

interface ApprovalResumeRetry {
  runId: string
  submission: FrozenApprovalSubmission
}

const TERMINAL_STATUSES = new Set<AgentRunStatus>([
  'completed',
  'insufficient_evidence',
  'rejected',
  'degraded',
  'failed',
  'error',
  'manual_review',
  'refused',
])

function normalizeStatus(status: string | null | undefined): AgentRunStatus {
  if (!status) return 'running'
  if (status === 'interrupted') return 'waiting_approval'
  if (status === 'error') return 'failed'
  return status as AgentRunStatus
}

type NonSuccessStatus = Extract<AgentRunStatus, 'failed' | 'error' | 'manual_review' | 'refused' | 'rejected'>

function isNonSuccessStatus(status: AgentRunStatus): status is NonSuccessStatus {
  return ['failed', 'error', 'manual_review', 'refused', 'rejected'].includes(status)
}

function assistantMessageStatus(status: AgentRunStatus): ChatMessage['status'] {
  return isNonSuccessStatus(status) ? 'error' : 'completed'
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
  const payloadStatus = normalizeStatus(event.payload?.final_status)
  if (event.event_type === 'error' && ['manual_review', 'refused'].includes(payloadStatus)) {
    return payloadStatus
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

  if (isNonSuccessStatus(status)) {
    return upsertTimelineEvent(steps, {
      event_type: 'error',
      run_id: runId,
      step_index: nextStepIndex(steps),
      node_name: 'error',
      status: status === 'failed' || status === 'error' ? 'failed' : status,
      message: '执行遇到问题，请重试',
      timestamp: new Date().toISOString(),
      payload: {
        error_message: errorMessage ?? finalResponse ?? DEFAULT_ERROR_MESSAGE,
        final_response: finalResponse ?? undefined,
        final_status: status,
      },
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
  const approvalResumeRetryRef = useRef<ApprovalResumeRetry | null>(null)

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
                status: assistantMessageStatus(recoveredStatus),
                runId,
              })
            : isNonSuccessStatus(recoveredStatus)
              ? updateAssistantMessage(current.messages, current.activeAssistantMessageId, {
                  content: DEFAULT_ERROR_MESSAGE,
                  status: 'error',
                  runId,
                })
              : current.messages,
          finalResponse: finalResponse ?? current.finalResponse,
          activeAssistantMessageId: TERMINAL_STATUSES.has(recoveredStatus) ? null : current.activeAssistantMessageId,
          error: isNonSuccessStatus(recoveredStatus) ? finalResponse ?? DEFAULT_ERROR_MESSAGE : null,
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
                      status: assistantMessageStatus(nextStatus),
                      runId,
                    })
                  : isNonSuccessStatus(nextStatus)
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
                error: isNonSuccessStatus(nextStatus) ? finalResponse ?? DEFAULT_ERROR_MESSAGE : null,
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
            const incomingContext = parseApprovalDecisionContext(event.payload?.decision_context)
            const envelopeApprovalId = event.payload?.approval_id
            const contextEnvelopeMatches = Boolean(
              incomingContext
              && incomingContext.run_id === runId
              && (!envelopeApprovalId || envelopeApprovalId === incomingContext.approval_id),
            )
            const replaceApprovalContext = Boolean(
              incomingContext
              && contextEnvelopeMatches
              && shouldReplaceApprovalDecisionContext(current.approvalContext, incomingContext),
            )
            const revalidateApprovalContext = Boolean(
              incomingContext
              && contextEnvelopeMatches
              && isExactApprovalDecisionContext(current.approvalContext, incomingContext),
            )
            const approvalContext = replaceApprovalContext ? incomingContext : current.approvalContext
            const approvalId = replaceApprovalContext ? incomingContext?.approval_id ?? null : current.approvalId
            const isApprovalEvent = event.event_type === 'approval_required' || nextStatus === 'waiting_approval'
            const approvalContextFresh = replaceApprovalContext || revalidateApprovalContext
              ? true
              : isApprovalEvent && !incomingContext
                ? false
                : current.approvalContextFresh
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
                  status: assistantMessageStatus(nextStatus),
                  runId,
                })
              : isNonSuccessStatus(nextStatus)
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
              approvalContextFresh,
              finalResponse,
              activeAssistantMessageId:
                event.event_type === 'final_response' || TERMINAL_STATUSES.has(nextStatus)
                  ? null
                  : current.activeAssistantMessageId,
              error: isNonSuccessStatus(nextStatus) ? errorMessage : null,
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
      approvalResumeRetryRef.current = null
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

  const applyAuthoritativeApproval = useCallback((approval: ApprovalRecord, revalidateExact = false) => {
    setState((current) => {
      const incoming = approval.decision_context
      if (!incoming) {
        return {
          ...current,
          approvalId: approval.id,
          approvalContext: null,
          approvalContextFresh: false,
        }
      }
      const replace = shouldReplaceApprovalDecisionContext(current.approvalContext, incoming)
      const revalidated = revalidateExact && isExactApprovalDecisionContext(current.approvalContext, incoming)
      return {
        ...current,
        approvalId: replace || revalidated ? approval.id : current.approvalId,
        approvalContext: replace ? incoming : current.approvalContext,
        approvalContextFresh: revalidated,
      }
    })
  }, [])

  const recordResumeIncomplete = useCallback(
    async (
      submission: FrozenApprovalSubmission,
      runId: string,
    ): Promise<ApprovalSubmissionOutcome> => {
      approvalResumeRetryRef.current = { submission, runId }
      const [latestApproval, latestRun] = await Promise.all([
        getApproval(submission.approval_id),
        getRunStatus(runId),
      ])
      const approval = latestApproval.success
        && latestApproval.data.id === submission.approval_id
        && latestApproval.data.run_id === runId
        && isTerminalApprovalStatus(latestApproval.data.status)
        ? latestApproval.data
        : null
      if (approval) applyAuthoritativeApproval(approval)
      const runStatus = latestRun.success ? latestRun.data.final_status : null
      setState((current) => ({
        ...current,
        approvalContextFresh: false,
        error: RESUME_INCOMPLETE_MESSAGE,
      }))
      return { kind: 'resume_incomplete', approval, runStatus }
    },
    [applyAuthoritativeApproval],
  )

  const recoverApprovalAfterSubmission = useCallback(
    async (
      approvalId: string,
      runId: string,
      unresolvedKind: 'stale' | 'ambiguous',
    ): Promise<ApprovalSubmissionOutcome> => {
      const latest = await getApproval(approvalId)
      if (!latest.success) {
        setState((current) => ({
          ...current,
          approvalContextFresh: false,
          error: unresolvedKind === 'ambiguous'
            ? '提交结果未确认，正在查询最新状态。请勿重复提交。'
            : '审批已更新，请刷新后重新决定。',
        }))
        return unresolvedKind === 'ambiguous'
          ? { kind: 'ambiguous', approval: null }
          : { kind: 'stale', approval: null }
      }

      applyAuthoritativeApproval(latest.data)
      if (latest.data.decision_context === null && isTerminalApprovalStatus(latest.data.status)) {
        setState((current) => ({
          ...current,
          status: latest.data.status === 'approved' ? 'running' : 'rejected',
          error: null,
        }))
        startPolling(runId)
        return { kind: 'reconciled', approval: latest.data }
      }
      setState((current) => ({
        ...current,
        error: unresolvedKind === 'ambiguous'
          ? '提交结果未确认，正在查询最新状态。请勿重复提交。'
          : '审批已更新，请基于最新内容重新决定。',
      }))
      return { kind: unresolvedKind, approval: latest.data }
    },
    [applyAuthoritativeApproval, startPolling],
  )

  const approveRun = useCallback(async (
    reviewedContext: ApprovalDecisionContextV1,
  ): Promise<ApprovalSubmissionOutcome> => {
    if (
      !state.runId
      || reviewedContext.run_id !== state.runId
      || reviewedContext.approval_id !== state.approvalId
    ) return { kind: 'unavailable', approval: null }
    const approvalId = reviewedContext.approval_id
    try {
      const latest = await getApproval(approvalId)
      if (!latest.success) {
        setState((current) => ({ ...current, approvalContextFresh: false, error: '审批不可用，请刷新后重试。' }))
        return { kind: 'unavailable', approval: null }
      }
      if (!latest.data.decision_context) {
        applyAuthoritativeApproval(latest.data)
        if (isTerminalApprovalStatus(latest.data.status)) {
          startPolling(state.runId)
          return { kind: 'reconciled', approval: latest.data }
        }
        return { kind: 'unavailable', approval: null }
      }
      if (!isExactApprovalDecisionContext(reviewedContext, latest.data.decision_context)) {
        applyAuthoritativeApproval(latest.data)
        return { kind: 'stale', approval: latest.data }
      }
      applyAuthoritativeApproval(latest.data, true)
      const frozen = reviewedContext
      const submission = freezeApprovalSubmission(frozen, { decision_type: 'approve' })
      const result = await submitFrozenApprovalSubmission(submission)
      if (!result.success) {
        if (result.error.code === 'APPROVAL_RESUME_FAILED') {
          return recordResumeIncomplete(submission, state.runId)
        }
        if (result.error.code === 'NETWORK_ERROR') {
          return recoverApprovalAfterSubmission(frozen.approval_id, state.runId, 'ambiguous')
        }
        if (result.error.code === 'HTTP_409' || result.error.code === 'CONFLICT') {
          return recoverApprovalAfterSubmission(frozen.approval_id, state.runId, 'stale')
        }
        setState((current) => ({ ...current, approvalContextFresh: false, error: '审批提交失败，请刷新后重试。' }))
        return { kind: 'unavailable', approval: null }
      }
      setState((current) => ({ ...current, status: 'running', approvalContextFresh: false, error: null }))
      startPolling(state.runId)
      return { kind: 'submitted' }
    } catch {
      setState((current) => ({ ...current, approvalContextFresh: false, error: '审批提交失败，请刷新后重试。' }))
      return { kind: 'unavailable', approval: null }
    }
  }, [applyAuthoritativeApproval, recordResumeIncomplete, recoverApprovalAfterSubmission, startPolling, state.approvalId, state.runId])

  const rejectRun = useCallback(
    async (reviewedContext: ApprovalDecisionContextV1, reason: string): Promise<ApprovalSubmissionOutcome> => {
      if (
        !state.runId
        || reviewedContext.run_id !== state.runId
        || reviewedContext.approval_id !== state.approvalId
        || !reason.trim()
      ) return { kind: 'unavailable', approval: null }
      const approvalId = reviewedContext.approval_id
      try {
        const latest = await getApproval(approvalId)
        if (!latest.success) {
          setState((current) => ({ ...current, approvalContextFresh: false, error: '审批不可用，请刷新后重试。' }))
          return { kind: 'unavailable', approval: null }
        }
        if (!latest.data.decision_context) {
          applyAuthoritativeApproval(latest.data)
          if (isTerminalApprovalStatus(latest.data.status)) {
            startPolling(state.runId)
            return { kind: 'reconciled', approval: latest.data }
          }
          return { kind: 'unavailable', approval: null }
        }
        if (!isExactApprovalDecisionContext(reviewedContext, latest.data.decision_context)) {
          applyAuthoritativeApproval(latest.data)
          return { kind: 'stale', approval: latest.data }
        }
        applyAuthoritativeApproval(latest.data, true)
        const frozen = reviewedContext
        const submission = freezeApprovalSubmission(frozen, { decision_type: 'reject', reason })
        const result = await submitFrozenApprovalSubmission(submission)
        if (!result.success) {
          if (result.error.code === 'APPROVAL_RESUME_FAILED') {
            return recordResumeIncomplete(submission, state.runId)
          }
          if (result.error.code === 'NETWORK_ERROR') {
            return recoverApprovalAfterSubmission(frozen.approval_id, state.runId, 'ambiguous')
          }
          if (result.error.code === 'HTTP_409' || result.error.code === 'CONFLICT') {
            return recoverApprovalAfterSubmission(frozen.approval_id, state.runId, 'stale')
          }
          setState((current) => ({ ...current, approvalContextFresh: false, error: '审批提交失败，请刷新后重试。' }))
          return { kind: 'unavailable', approval: null }
        }
        setState((current) => ({
          ...current,
          status: 'rejected',
          approvalContextFresh: false,
          messages: updateAssistantMessage(current.messages, current.activeAssistantMessageId, {
            content: `审批已拒绝：${reason}`,
            status: 'error',
          }),
          activeAssistantMessageId: null,
          error: reason,
        }))
        startPolling(state.runId)
        return { kind: 'submitted' }
      } catch {
        setState((current) => ({ ...current, approvalContextFresh: false, error: '审批提交失败，请刷新后重试。' }))
        return { kind: 'unavailable', approval: null }
      }
    },
    [applyAuthoritativeApproval, recordResumeIncomplete, recoverApprovalAfterSubmission, startPolling, state.approvalId, state.runId],
  )

  const retryApprovalResume = useCallback(async (): Promise<ApprovalSubmissionOutcome> => {
    const retry = approvalResumeRetryRef.current
    if (!retry || retry.runId !== state.runId) return { kind: 'unavailable', approval: null }
    try {
      const result = await submitFrozenApprovalSubmission(retry.submission)
      if (result.success) {
        approvalResumeRetryRef.current = null
        setState((current) => ({
          ...current,
          status: 'running',
          approvalContextFresh: false,
          error: null,
        }))
        startPolling(retry.runId)
        return { kind: 'resume_reconciled', approval: result.data }
      }
      if (result.error.code === 'APPROVAL_RESUME_FAILED') {
        return recordResumeIncomplete(retry.submission, retry.runId)
      }
      if (result.error.code === 'NETWORK_ERROR') {
        setState((current) => ({
          ...current,
          approvalContextFresh: false,
          error: '恢复结果未确认，请勿重复点击；可查询最新状态后再决定。',
        }))
        return { kind: 'ambiguous', approval: null }
      }
      approvalResumeRetryRef.current = null
      setState((current) => ({
        ...current,
        approvalContextFresh: false,
        error: '运行恢复请求已失效，请刷新后联系管理员。',
      }))
      return result.error.code === 'HTTP_409' || result.error.code === 'CONFLICT'
        ? { kind: 'stale', approval: null }
        : { kind: 'unavailable', approval: null }
    } catch {
      setState((current) => ({
        ...current,
        approvalContextFresh: false,
        error: '恢复结果未确认，请勿重复点击；可查询最新状态后再决定。',
      }))
      return { kind: 'ambiguous', approval: null }
    }
  }, [recordResumeIncomplete, startPolling, state.runId])

  const reset = useCallback(() => {
    runGenerationRef.current += 1
    approvalResumeRetryRef.current = null
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
    retryApprovalResume,
    reset,
    newConversation,
    resetConversation: newConversation,
  }
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import {
  decideApproval,
  freezeApprovalSubmission,
  getApproval,
  getPendingApprovals,
  getRunStatus,
  isExactApprovalDecisionContext,
  isTerminalApprovalStatus,
  shouldReplaceApprovalDecisionContext,
  submitFrozenApprovalSubmission,
} from '@/lib/api'
import type {
  ApprovalDecisionContextV1,
  ApprovalRecord,
  ApprovalSubmissionOutcome,
  FrozenApprovalSubmission,
} from '@/lib/api'

interface ApprovalTabProps {
  approvalId: string | null
  proposedAction?: Record<string, unknown> | null
  riskLevel?: string | null
  canApprove: boolean
  status: string
  latestDecisionContext?: ApprovalDecisionContextV1 | null
  onApprove?: (reviewedContext: ApprovalDecisionContextV1) => Promise<ApprovalSubmissionOutcome>
  onReject?: (reviewedContext: ApprovalDecisionContextV1, reason: string) => Promise<ApprovalSubmissionOutcome>
  onRetryResume?: () => Promise<ApprovalSubmissionOutcome>
}

type PendingDecision = 'approve' | 'reject' | 'resume' | null
type ResumeRetry =
  | { source: 'active' }
  | { source: 'direct'; submission: FrozenApprovalSubmission }

const RESUME_INCOMPLETE_MESSAGE = '审批决定已保存，但运行恢复未完成。系统不会自动重复提交审批决定。'

function riskVariant(riskLevel?: string | null) {
  if (riskLevel === 'high') return 'destructive'
  if (riskLevel === 'medium') return 'warning'
  return 'outline'
}

function actionEntries(proposedAction?: Record<string, unknown> | null) {
  if (!proposedAction) return []
  return Object.entries(proposedAction).filter(([, value]) => value !== null && value !== undefined && value !== '')
}

function reconciledApprovalMessage(approval: ApprovalRecord) {
  if (approval.status === 'approved') return '服务器已确认审批通过，正在同步运行状态。'
  if (approval.status === 'rejected') return '服务器已确认审批驳回。'
  return `服务器已确认审批终态：${approval.status}。`
}

async function queryResumeIncompleteState(
  submission: FrozenApprovalSubmission,
): Promise<ApprovalSubmissionOutcome> {
  const [latestApproval, latestRun] = await Promise.all([
    getApproval(submission.approval_id),
    getRunStatus(submission.run_id),
  ])
  const approval = latestApproval.success
    && latestApproval.data.id === submission.approval_id
    && latestApproval.data.run_id === submission.run_id
    && isTerminalApprovalStatus(latestApproval.data.status)
    ? latestApproval.data
    : null
  return {
    kind: 'resume_incomplete',
    approval,
    runStatus: latestRun.success ? latestRun.data.final_status : null,
  }
}

export function ApprovalTab({
  approvalId,
  canApprove,
  status,
  latestDecisionContext,
  onApprove,
  onReject,
  onRetryResume,
}: ApprovalTabProps) {
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRecord[]>([])
  const [selectedApprovalId, setSelectedApprovalId] = useState<string | null>(null)
  const [activeApproval, setActiveApproval] = useState<ApprovalRecord | null>(null)
  const [loadingList, setLoadingList] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [detailRefresh, setDetailRefresh] = useState(0)
  const [contextInvalidated, setContextInvalidated] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [pendingDecision, setPendingDecision] = useState<PendingDecision>(null)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [resumeRetry, setResumeRetry] = useState<ResumeRetry | null>(null)
  const loadPendingApprovals = useCallback(async () => {
    if (!canApprove) {
      setPendingApprovals([])
      setSelectedApprovalId(null)
      setLoadError(null)
      return
    }

    setLoadingList(true)
    const result = await getPendingApprovals()
    setLoadingList(false)
    if (!result.success) {
      setLoadError(result.error?.message ?? '待审批列表加载失败')
      return
    }
    setPendingApprovals(result.data.approvals)
    setLoadError(null)
    setSelectedApprovalId((current) => {
      if (current && result.data.approvals.some((approval) => approval.id === current)) {
        return current
      }
      const currentRunApproval = result.data.approvals.find((approval) => approval.id === approvalId)
      return currentRunApproval?.id ?? result.data.approvals[0]?.id ?? null
    })
  }, [approvalId, canApprove])
  const displayedContext = activeApproval?.decision_context ?? null
  const entries = useMemo(() => actionEntries(displayedContext?.proposed_action), [displayedContext])
  const decisionCopy =
    pendingDecision === 'approve'
      ? '确认批准此操作？系统将创建已授权的操作草稿；本页面不会直接执行生产外部操作。'
      : pendingDecision === 'reject'
        ? '确认驳回此操作？请填写驳回原因。'
        : '确认重试恢复运行？系统将使用已保存的同一审批决定恢复运行，不会重新审批，也不会直接执行生产外部操作。'

  useEffect(() => {
    void Promise.resolve()
      .then(() => loadPendingApprovals())
      .catch(() => setLoadError('待审批列表加载失败'))
  }, [loadPendingApprovals])

  useEffect(() => {
    if (!canApprove || !selectedApprovalId) {
      setActiveApproval(null)
      return
    }
    let active = true
    setLoadingDetail(true)
    setContextInvalidated(true)
    setActiveApproval(null)
    void getApproval(selectedApprovalId).then((result) => {
      if (!active) return
      setLoadingDetail(false)
      if (!result.success) {
        setLoadError(result.error.message || '审批信息加载失败，请重试。')
        return
      }
      setActiveApproval(result.data)
      setContextInvalidated(false)
      setLoadError(null)
    })
    return () => { active = false }
  }, [canApprove, detailRefresh, selectedApprovalId])

  useEffect(() => {
    if (
      !displayedContext
      || !latestDecisionContext
      || displayedContext.approval_id !== latestDecisionContext.approval_id
      || isExactApprovalDecisionContext(displayedContext, latestDecisionContext)
      || !shouldReplaceApprovalDecisionContext(displayedContext, latestDecisionContext)
    ) {
      return
    }
    setContextInvalidated(true)
    setPendingDecision(null)
    setStatusMessage('审批内容已更新，请刷新并重新复核后再决定。')
  }, [displayedContext, latestDecisionContext])

  async function confirmDecision() {
    const decision = pendingDecision
    if (!decision || submitting) return
    if (decision !== 'resume' && (!activeApproval?.decision_context || contextInvalidated)) return
    if (decision === 'resume' && !resumeRetry) return
    setSubmitting(true)
    setStatusMessage(null)
    let outcome: ApprovalSubmissionOutcome = { kind: 'unavailable', approval: null }
    let newResumeRetry: ResumeRetry | null = null
    try {
      if (decision === 'resume' && resumeRetry) {
        if (resumeRetry.source === 'active') {
          outcome = onRetryResume
            ? await onRetryResume()
            : { kind: 'unavailable', approval: null }
        } else {
          const result = await submitFrozenApprovalSubmission(resumeRetry.submission)
          if (result.success) {
            outcome = { kind: 'resume_reconciled', approval: result.data }
          } else if (result.error.code === 'APPROVAL_RESUME_FAILED') {
            outcome = await queryResumeIncompleteState(resumeRetry.submission)
          } else if (result.error.code === 'NETWORK_ERROR') {
            outcome = { kind: 'ambiguous', approval: null }
          } else if (result.error.code === 'HTTP_409' || result.error.code === 'CONFLICT') {
            outcome = { kind: 'stale', approval: null }
          }
        }
      } else {
        const frozenContext = structuredClone(activeApproval!.decision_context!)
        const input = decision === 'approve'
          ? { decision_type: 'approve' as const }
          : { decision_type: 'reject' as const, reason }
        const submission = freezeApprovalSubmission(frozenContext, input)
        const activeCallback = activeApproval!.id === approvalId
          ? decision === 'approve'
            ? onApprove
            : onReject
          : undefined
        if (activeCallback) {
          outcome = decision === 'approve'
            ? await (activeCallback as NonNullable<typeof onApprove>)(frozenContext)
            : await (activeCallback as NonNullable<typeof onReject>)(frozenContext, reason)
          if (outcome.kind === 'resume_incomplete') newResumeRetry = { source: 'active' }
        } else {
          const result = await decideApproval(frozenContext, input)
          if (result.success) {
            outcome = { kind: 'submitted' }
          } else if (result.error.code === 'APPROVAL_RESUME_FAILED') {
            newResumeRetry = { source: 'direct', submission }
            outcome = await queryResumeIncompleteState(submission)
          } else if (result.error.code === 'NETWORK_ERROR') {
            const latest = await getApproval(frozenContext.approval_id)
            if (latest.success && latest.data.decision_context === null && isTerminalApprovalStatus(latest.data.status)) {
              outcome = { kind: 'reconciled', approval: latest.data }
            } else {
              outcome = { kind: 'ambiguous', approval: latest.success ? latest.data : null }
            }
          } else if (result.error.code === 'HTTP_409' || result.error.code === 'CONFLICT') {
            const latest = await getApproval(frozenContext.approval_id)
            if (latest.success && latest.data.decision_context === null && isTerminalApprovalStatus(latest.data.status)) {
              outcome = { kind: 'reconciled', approval: latest.data }
            } else {
              outcome = { kind: 'stale', approval: latest.success ? latest.data : null }
            }
          } else {
            outcome = { kind: 'unavailable', approval: null }
          }
        }
      }
    } catch {
      outcome = { kind: 'unavailable', approval: null }
    }

    if (outcome.kind === 'submitted') {
      setResumeRetry(null)
      setContextInvalidated(true)
      setStatusMessage('审批决定已提交，正在同步运行状态。')
      await loadPendingApprovals()
    } else if (outcome.kind === 'resume_reconciled') {
      setResumeRetry(null)
      setContextInvalidated(true)
      if (outcome.approval) setActiveApproval(outcome.approval)
      setStatusMessage('运行恢复流程已完成，请查看权威运行终态。')
    } else if (outcome.kind === 'resume_incomplete') {
      if (decision !== 'resume') setResumeRetry(newResumeRetry)
      setContextInvalidated(true)
      if (outcome.approval) setActiveApproval(outcome.approval)
      setStatusMessage(RESUME_INCOMPLETE_MESSAGE)
    } else if (outcome.kind === 'reconciled') {
      setResumeRetry(null)
      setContextInvalidated(true)
      setActiveApproval(outcome.approval)
      setStatusMessage(reconciledApprovalMessage(outcome.approval))
      await loadPendingApprovals()
    } else if (outcome.kind === 'stale') {
      if (decision === 'resume') setResumeRetry(null)
      setContextInvalidated(true)
      setActiveApproval(outcome.approval)
      setStatusMessage('审批已更新，请查看最新内容后重新决定。')
    } else if (outcome.kind === 'ambiguous') {
      setContextInvalidated(true)
      setActiveApproval(outcome.approval)
      setStatusMessage('提交结果未确认，已查询最新状态。请勿重复提交。')
    } else {
      if (decision === 'resume') setResumeRetry(null)
      setContextInvalidated(true)
      setActiveApproval(null)
      setLoadError('审批不可用或已更新，请返回列表并刷新。')
    }
    setPendingDecision(null)
    setReason('')
    setSubmitting(false)
  }

  const context = displayedContext
  const expired = context ? Date.parse(context.expires_at) <= Date.now() : true
  const canApproveDecision = Boolean(
    context
    && !contextInvalidated
    && activeApproval?.status === 'pending'
    && !expired
    && context.allowed_decision_types.includes('approve'),
  )
  const canRejectDecision = Boolean(
    context
    && !contextInvalidated
    && activeApproval?.status === 'pending'
    && !expired
    && context.allowed_decision_types.includes('reject'),
  )

  return (
    <div className="space-y-4">
      {!canApprove ? (
        <Card>
          <CardHeader>
            <CardTitle>审批状态</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-body text-muted-foreground">
              当前角色没有审批权限。需要审批员或管理员查看待审批列表并处理该请求。
            </p>
            {approvalId ? (
              <div className="mt-3 grid grid-cols-[88px_1fr] gap-3 text-label">
                <span className="text-muted-foreground">approval</span>
                <span className="min-w-0 break-all">{approvalId}</span>
                <span className="text-muted-foreground">status</span>
                <Badge variant={status === 'waiting_approval' ? 'warning' : 'outline'}>{status}</Badge>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>待审批列表</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {!canApprove ? (
            <p className="text-body text-muted-foreground">切换到审批员或管理员后可查看待审批列表。</p>
          ) : loadingList ? (
            <p className="text-body text-muted-foreground" aria-live="polite">正在加载待审批项…</p>
          ) : loadError ? (
            <div className="rounded-md border border-destructive/40 p-3 text-body" role="alert">{loadError}</div>
          ) : pendingApprovals.length === 0 ? (
            <p className="text-body text-muted-foreground">当前没有待处理审批</p>
          ) : (
            pendingApprovals.map((approval) => (
              <button
                key={approval.id}
                type="button"
                className={`w-full rounded-md border p-3 text-left text-body transition-colors ${
                  activeApproval?.id === approval.id ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/40'
                }`}
                onClick={() => {
                  setSelectedApprovalId(approval.id)
                  setDetailRefresh((current) => current + 1)
                }}
                aria-pressed={selectedApprovalId === approval.id}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold">run {approval.run_id.slice(0, 8)}</span>
                  <Badge variant={riskVariant(approval.risk_level)}>{approval.risk_level}</Badge>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-label text-muted-foreground">
                  <span>{approval.risk_rule_ref ?? 'rule n/a'}</span>
                  <span>{new Date(approval.created_at).toLocaleString()}</span>
                  <span>{approval.id}</span>
                </div>
              </button>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <CardTitle>审批操作</CardTitle>
          <Badge variant={riskVariant(activeApproval?.risk_level)}>
            risk_level: {canApprove ? context?.risk_level ?? 'unknown' : 'hidden'}
          </Badge>
        </CardHeader>
        <CardContent>
          {!canApprove ? (
            <p className="text-body text-muted-foreground">审批详情仅对审批员和管理员可见。</p>
          ) : loadingDetail ? (
            <p className="text-body text-muted-foreground" aria-live="polite">正在加载审批详情…</p>
          ) : entries.length > 0 ? (
            <dl className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-2 text-body">
              {entries.map(([key, value]) => (
                <div key={key} className="contents">
                  <dt className="text-muted-foreground">{key}</dt>
                  <dd className="min-w-0 break-words">
                    {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-body text-muted-foreground">审批信息不完整，请刷新后再决定。</p>
          )}
        </CardContent>
      </Card>

      {canApprove ? (
        <div className="grid grid-cols-2 gap-3">
          <Button
            className="min-h-11"
            disabled={submitting || !canApproveDecision}
            aria-disabled={submitting || !canApproveDecision}
            onClick={() => setPendingDecision('approve')}
          >
            批准
          </Button>
          <Button
            className="min-h-11"
            variant="destructive"
            disabled={submitting || !canRejectDecision}
            aria-disabled={submitting || !canRejectDecision}
            onClick={() => setPendingDecision('reject')}
          >
            驳回
          </Button>
        </div>
      ) : null}

      {canApprove && contextInvalidated && activeApproval?.status === 'pending' && selectedApprovalId ? (
        <Button
          className="min-h-11 w-full"
          variant="outline"
          disabled={loadingDetail || submitting}
          onClick={() => setDetailRefresh((current) => current + 1)}
        >
          刷新并复核最新审批
        </Button>
      ) : null}

      {canApprove && resumeRetry ? (
        <Card>
          <CardContent className="space-y-3" role="alert">
            <p className="text-body text-status-waiting">{RESUME_INCOMPLETE_MESSAGE}</p>
            <Button
              className="min-h-11"
              variant="outline"
              disabled={submitting}
              onClick={() => setPendingDecision('resume')}
            >
              重试恢复运行
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {statusMessage ? <p aria-live="polite" className="text-body text-muted-foreground">{statusMessage}</p> : null}

      <Dialog open={pendingDecision !== null} onOpenChange={(open) => !open && setPendingDecision(null)}>
        <DialogContent>
          <DialogClose onOpenChange={(open) => !open && setPendingDecision(null)} />
          <DialogHeader>
            <DialogTitle>
              {pendingDecision === 'approve'
                ? '确认批准'
                : pendingDecision === 'reject'
                  ? '确认驳回'
                  : '确认重试恢复'}
            </DialogTitle>
          </DialogHeader>
          <div className="px-4 py-3">
            <p className="text-body text-muted-foreground">{decisionCopy}</p>
            {pendingDecision === 'reject' ? (
              <div>
                <Textarea
                  className="mt-3"
                  rows={3}
                  value={reason}
                  placeholder="请输入驳回原因"
                  aria-label="驳回原因"
                  aria-describedby="reject-reason-help"
                  onChange={(event) => setReason(event.target.value)}
                />
                <p id="reject-reason-help" className="mt-2 text-label text-muted-foreground">
                  驳回决定必须填写非空原因。
                </p>
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" disabled={submitting} onClick={() => setPendingDecision(null)}>
              取消
            </Button>
            <Button
              variant={pendingDecision === 'reject' ? 'destructive' : 'default'}
              disabled={
                submitting
                || (pendingDecision !== 'resume' && contextInvalidated)
                || (pendingDecision === 'reject' && !reason.trim())
              }
              onClick={() => void confirmDecision()}
            >
              {submitting
                ? '提交中…'
                : pendingDecision === 'approve'
                  ? '批准'
                  : pendingDecision === 'reject'
                    ? '驳回'
                    : '重试恢复'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

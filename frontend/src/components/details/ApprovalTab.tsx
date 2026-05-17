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
import { decideApproval, getPendingApprovals } from '@/lib/api'
import type { ApprovalRecord } from '@/lib/api'

interface ApprovalTabProps {
  approvalId: string | null
  proposedAction?: Record<string, unknown> | null
  riskLevel?: string | null
  canApprove: boolean
  status: string
  onApprove?: () => void | Promise<void>
  onReject?: (reason: string) => void | Promise<void>
}

type PendingDecision = 'approve' | 'reject' | null

function riskVariant(riskLevel?: string | null) {
  if (riskLevel === 'high') return 'destructive'
  if (riskLevel === 'medium') return 'warning'
  return 'outline'
}

function actionEntries(proposedAction?: Record<string, unknown> | null) {
  if (!proposedAction) return []
  return Object.entries(proposedAction).filter(([, value]) => value !== null && value !== undefined && value !== '')
}

export function ApprovalTab({
  approvalId,
  proposedAction,
  riskLevel,
  canApprove,
  status,
  onApprove,
  onReject,
}: ApprovalTabProps) {
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRecord[]>([])
  const [selectedApprovalId, setSelectedApprovalId] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [pendingDecision, setPendingDecision] = useState<PendingDecision>(null)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const loadPendingApprovals = useCallback(async () => {
    if (!canApprove) {
      setPendingApprovals([])
      setSelectedApprovalId(null)
      setLoadError(null)
      return
    }

    const result = await getPendingApprovals()
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
  const activeApproval = useMemo(() => {
    if (!canApprove) return null

    const selectedApproval = pendingApprovals.find((approval) => approval.id === selectedApprovalId)
    const currentRunApproval = pendingApprovals.find((approval) => approval.id === approvalId)
    return (
      selectedApproval ??
      currentRunApproval ??
      (approvalId
        ? {
            id: approvalId,
            run_id: '',
            status: status === 'waiting_approval' ? 'pending' : status,
            requested_by: '',
            proposed_action: proposedAction ?? {},
            risk_level: riskLevel ?? 'unknown',
            risk_rule_ref: null,
            risk_reason: null,
            decision: null,
            reason: null,
            decided_by: null,
            decided_at: null,
            expires_at: '',
            created_at: '',
          }
        : null)
    )
  }, [approvalId, canApprove, pendingApprovals, proposedAction, riskLevel, selectedApprovalId, status])
  const entries = useMemo(() => actionEntries(activeApproval?.proposed_action), [activeApproval])
  const decisionCopy =
    pendingDecision === 'approve'
      ? '确认批准此操作？批准后将立即执行，此操作不可撤销。'
      : '确认驳回此操作？驳回后本次请求将终止，此操作不可撤销。'

  useEffect(() => {
    void Promise.resolve()
      .then(() => loadPendingApprovals())
      .catch(() => setLoadError('待审批列表加载失败'))
  }, [loadPendingApprovals])

  async function confirmDecision() {
    if (!activeApproval || !pendingDecision) return
    setSubmitting(true)
    try {
      if (pendingDecision === 'approve') {
        if (activeApproval.id === approvalId && onApprove) {
          await onApprove()
        } else {
          await decideApproval(activeApproval.id, 'approve', 'Approved from MOCA demo console')
          await loadPendingApprovals()
        }
      } else if (activeApproval.id === approvalId && onReject) {
        await onReject(reason)
      } else {
        await decideApproval(activeApproval.id, 'reject', reason)
        await loadPendingApprovals()
      }
      setPendingDecision(null)
      setReason('')
    } catch {
      setLoadError('审批提交失败')
    } finally {
      setSubmitting(false)
    }
  }

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
          ) : loadError ? (
            <div className="rounded-md border border-destructive/40 p-3 text-body">{loadError}</div>
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
                onClick={() => setSelectedApprovalId(approval.id)}
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
            risk_level: {canApprove ? activeApproval?.risk_level ?? 'unknown' : 'hidden'}
          </Badge>
        </CardHeader>
        <CardContent>
          {!canApprove ? (
            <p className="text-body text-muted-foreground">审批详情仅对审批员和管理员可见。</p>
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
            <p className="text-body text-muted-foreground">等待 approval_required 事件中的 proposed_action 详情</p>
          )}
        </CardContent>
      </Card>

      {canApprove ? (
        <div className="grid grid-cols-2 gap-3">
          <Button
            className="min-h-11"
            disabled={submitting || !activeApproval || activeApproval.status !== 'pending'}
            onClick={() => setPendingDecision('approve')}
          >
            批准
          </Button>
          <Button
            className="min-h-11"
            variant="destructive"
            disabled={submitting || !activeApproval || activeApproval.status !== 'pending'}
            onClick={() => setPendingDecision('reject')}
          >
            驳回
          </Button>
        </div>
      ) : null}

      <Dialog open={pendingDecision !== null} onOpenChange={(open) => !open && setPendingDecision(null)}>
        <DialogContent>
          <DialogClose onOpenChange={(open) => !open && setPendingDecision(null)} />
          <DialogHeader>
            <DialogTitle>{pendingDecision === 'approve' ? '确认批准' : '确认驳回'}</DialogTitle>
          </DialogHeader>
          <div className="px-4 py-3">
            <p className="text-body text-muted-foreground">{decisionCopy}</p>
            {pendingDecision === 'reject' ? (
              <Textarea
                className="mt-3"
                rows={3}
                value={reason}
                placeholder="请输入驳回原因"
                onChange={(event) => setReason(event.target.value)}
              />
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" disabled={submitting} onClick={() => setPendingDecision(null)}>
              取消
            </Button>
            <Button
              variant={pendingDecision === 'reject' ? 'destructive' : 'default'}
              disabled={submitting || (pendingDecision === 'reject' && !reason.trim())}
              onClick={() => void confirmDecision()}
            >
              {pendingDecision === 'approve' ? '批准' : '驳回'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

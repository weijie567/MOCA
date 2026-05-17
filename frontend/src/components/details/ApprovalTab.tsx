import { useMemo, useState } from 'react'
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
import { decideApproval } from '@/lib/api'

interface ApprovalTabProps {
  approvalId: string | null
  proposedAction?: Record<string, unknown> | null
  riskLevel?: string | null
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
  status,
  onApprove,
  onReject,
}: ApprovalTabProps) {
  const [pendingDecision, setPendingDecision] = useState<PendingDecision>(null)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const entries = useMemo(() => actionEntries(proposedAction), [proposedAction])
  const decisionCopy =
    pendingDecision === 'approve'
      ? '确认批准此操作？批准后将立即执行，此操作不可撤销。'
      : '确认驳回此操作？驳回后本次请求将终止，此操作不可撤销。'

  async function confirmDecision() {
    if (!approvalId || !pendingDecision) return
    setSubmitting(true)
    if (pendingDecision === 'approve') {
      if (onApprove) {
        await onApprove()
      } else {
        await decideApproval(approvalId, 'approve', 'Approved from MOCA demo console')
      }
    } else if (onReject) {
      await onReject(reason)
    } else {
      await decideApproval(approvalId, 'reject', reason)
    }
    setSubmitting(false)
    setPendingDecision(null)
  }

  if (!approvalId) {
    return (
      <div className="rounded-md border border-dashed border-border p-4 text-body text-muted-foreground">
        当前没有待处理审批
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <CardTitle>审批操作</CardTitle>
          <Badge variant={riskVariant(riskLevel)}>risk_level: {riskLevel ?? 'unknown'}</Badge>
        </CardHeader>
        <CardContent>
          {entries.length > 0 ? (
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

      <div className="grid grid-cols-2 gap-3">
        <Button className="min-h-11" disabled={submitting || status !== 'waiting_approval'} onClick={() => setPendingDecision('approve')}>
          批准
        </Button>
        <Button
          className="min-h-11"
          variant="destructive"
          disabled={submitting || status !== 'waiting_approval'}
          onClick={() => setPendingDecision('reject')}
        >
          驳回
        </Button>
      </div>

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

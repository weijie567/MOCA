import { useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { DemoRole } from '@/hooks/useAuth'
import type { ApprovalSubmissionOutcome } from '@/lib/api'
import type { SseEvent } from '@/types/events'
import { ApprovalTab } from './ApprovalTab'
import { BusinessQueryResultTab } from './BusinessQueryResultTab'
import { EvidenceTab } from './EvidenceTab'
import { TraceTab } from './TraceTab'

type DetailsTab = 'result' | 'evidence' | 'approval' | 'trace' | 'run'

interface DetailsPanelProps {
  runId: string | null
  approvalId: string | null
  role: DemoRole
  status: string
  steps?: SseEvent[]
  approveRun?: () => Promise<ApprovalSubmissionOutcome>
  rejectRun?: (reason: string) => Promise<ApprovalSubmissionOutcome>
  retryApprovalResume?: () => Promise<ApprovalSubmissionOutcome>
}

function statusVariant(status: string) {
  if (status === 'completed') return 'success'
  if (status === 'waiting_approval' || status === 'interrupted' || status === 'degraded' || status === 'manual_review') return 'warning'
  if (status === 'failed' || status === 'error' || status === 'rejected' || status === 'refused') return 'destructive'
  if (status === 'idle') return 'secondary'
  return 'default'
}

export function DetailsPanel({
  runId,
  approvalId,
  role,
  status,
  steps = [],
  approveRun,
  rejectRun,
  retryApprovalResume,
}: DetailsPanelProps) {
  const [activeTab, setActiveTab] = useState<DetailsTab>('result')
  const selectedTab = status === 'waiting_approval' ? 'approval' : activeTab

  const approvalEvent = useMemo(
    () => [...steps].reverse().find((step) => step.event_type === 'approval_required'),
    [steps],
  )
  const detailsRefreshKey = `${status}-${steps
    .map((step) => `${step.node_name ?? step.event_type}:${step.status}:${step.timestamp}`)
    .join('|')}`

  return (
    <section className="flex min-h-0 min-w-0 flex-col bg-background">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-heading font-semibold">Details</h2>
        <p className="mt-1 text-label text-muted-foreground">Result / Evidence / Approval / Trace / Run Info</p>
      </div>

      <Tabs value={selectedTab} onValueChange={(value) => setActiveTab(value as DetailsTab)} className="flex min-h-0 flex-1 flex-col">
        <TabsList>
          <TabsTrigger value="result" activeValue={selectedTab} onValueChange={(value) => setActiveTab(value as DetailsTab)}>
            Result
          </TabsTrigger>
          <TabsTrigger value="evidence" activeValue={selectedTab} onValueChange={(value) => setActiveTab(value as DetailsTab)}>
            Evidence
          </TabsTrigger>
          <TabsTrigger value="approval" activeValue={selectedTab} onValueChange={(value) => setActiveTab(value as DetailsTab)}>
            Approval
          </TabsTrigger>
          <TabsTrigger value="trace" activeValue={selectedTab} onValueChange={(value) => setActiveTab(value as DetailsTab)}>
            Trace
          </TabsTrigger>
          <TabsTrigger value="run" activeValue={selectedTab} onValueChange={(value) => setActiveTab(value as DetailsTab)}>
            Run Info
          </TabsTrigger>
        </TabsList>

        <ScrollArea className="flex-1 p-4">
          <TabsContent value="result" activeValue={selectedTab}>
            <BusinessQueryResultTab steps={steps} />
          </TabsContent>
          <TabsContent value="evidence" activeValue={selectedTab}>
            <EvidenceTab runId={runId} refreshKey={detailsRefreshKey} />
          </TabsContent>
          <TabsContent value="approval" activeValue={selectedTab}>
            <ApprovalTab
              approvalId={approvalId}
              proposedAction={approvalEvent?.payload?.proposed_action ?? null}
              riskLevel={approvalEvent?.payload?.risk_level ?? null}
              canApprove={role === 'manager' || role === 'admin'}
              status={status}
              onApprove={approveRun}
              onReject={rejectRun}
              onRetryResume={retryApprovalResume}
            />
          </TabsContent>
          <TabsContent value="trace" activeValue={selectedTab}>
            <TraceTab runId={runId} refreshKey={detailsRefreshKey} />
          </TabsContent>
          <TabsContent value="run" activeValue={selectedTab}>
            <Card>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-label text-muted-foreground">status</span>
                  <Badge variant={statusVariant(status)}>{status}</Badge>
                </div>
                <div className="grid grid-cols-[88px_1fr] gap-3 text-body">
                  <span className="text-muted-foreground">run_id</span>
                  <span className="min-w-0 break-all">{runId ?? '-'}</span>
                  <span className="text-muted-foreground">approval</span>
                  <span className="min-w-0 break-all">{approvalId ?? '-'}</span>
                  <span className="text-muted-foreground">events</span>
                  <span>{steps.length}</span>
                  <span className="text-muted-foreground">mode</span>
                  <Badge variant="warning">演示模式</Badge>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </ScrollArea>
      </Tabs>
    </section>
  )
}

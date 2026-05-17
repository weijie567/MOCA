import { WifiOff } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { TimelineStep } from './TimelineStep'
import type { RunStatus, SseEvent } from '@/types/events'

interface AgentTimelineProps {
  steps: SseEvent[]
  status: RunStatus | 'idle'
}

export function AgentTimeline({ steps, status }: AgentTimelineProps) {
  return (
    <section className="flex min-h-0 min-w-0 flex-col border-r border-border bg-card/40">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-heading font-semibold">Agent Timeline</h2>
        <p className="mt-1 text-label text-muted-foreground">SSE 实时节点执行状态</p>
      </div>

      {status === 'disconnected' ? (
        <div className="mx-4 mt-4 flex items-center gap-2 rounded-md border border-status-disconnected bg-muted px-3 py-2 text-body text-muted-foreground">
          <WifiOff className="h-4 w-4" aria-hidden="true" />
          连接中断，正在恢复状态
        </div>
      ) : null}

      <ScrollArea className="flex-1 px-4 py-4">
        {steps.length === 0 ? (
          <div className="flex min-h-[360px] items-center justify-center rounded-md border border-dashed border-border text-body text-muted-foreground">
            等待提交问题后开始执行
          </div>
        ) : (
          <ol>
            {steps.map((step, index) => (
              <TimelineStep
                key={`${step.event_type}-${step.step_index}-${index}`}
                step={step}
                isLast={index === steps.length - 1}
              />
            ))}
          </ol>
        )}
      </ScrollArea>
    </section>
  )
}

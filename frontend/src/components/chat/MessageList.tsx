import { useEffect, useRef } from 'react'
import { Bot, UserRound } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

interface MessageListProps {
  queries: string[]
  finalResponse: string | null
  status: string
  error: string | null
}

function isRunning(status: string) {
  return status === 'running' || status === 'pending'
}

export function MessageList({ queries, finalResponse, status, error }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [queries.length, finalResponse, status, error])

  if (queries.length === 0) {
    return (
      <ScrollArea className="flex-1">
        <div className="flex h-full min-h-[360px] flex-col justify-center px-6 text-center">
          <p className="text-heading font-semibold">开始一个退款咨询</p>
          <p className="mt-2 text-body text-muted-foreground">
            输入订单号或退款问题，Agent 将检索规则并给出处理建议。例如：请给 ORD-2024-001 补偿 600 元
          </p>
        </div>
      </ScrollArea>
    )
  }

  return (
    <ScrollArea className="flex-1 px-4 py-4">
      <div className="space-y-4">
        {queries.map((query, index) => (
          <div key={`${query}-${index}`} className="flex justify-end">
            <div className="max-w-[86%] overflow-hidden rounded-md border border-border bg-muted px-3 py-2">
              <div className="mb-1 flex items-center justify-end gap-2 text-label text-muted-foreground">
                <span>用户</span>
                <UserRound className="h-3.5 w-3.5" aria-hidden="true" />
              </div>
              <p className="whitespace-pre-wrap break-words text-body">{query}</p>
            </div>
          </div>
        ))}

        {isRunning(status) ? (
          <div className="flex justify-start">
            <div className="max-w-[86%] overflow-hidden rounded-md border border-border bg-card px-3 py-3">
              <div className="mb-2 flex items-center gap-2 text-label text-muted-foreground">
                <Bot className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Agent</span>
              </div>
              <div className="space-y-2">
                <div className="h-2 w-56 animate-pulse rounded bg-muted" />
                <div className="h-2 w-40 animate-pulse rounded bg-muted" />
              </div>
            </div>
          </div>
        ) : null}

        {finalResponse ? (
          <div className="flex justify-start">
            <div className="max-w-[86%] overflow-hidden rounded-md border border-border bg-card px-3 py-2">
              <div className="mb-1 flex items-center gap-2 text-label text-muted-foreground">
                <Bot className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Agent</span>
              </div>
              <p className="whitespace-pre-wrap break-words text-body">{finalResponse}</p>
            </div>
          </div>
        ) : null}

        {error ? (
          <div
            className={cn(
              'rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-body text-destructive-foreground',
              'text-left',
            )}
          >
            执行遇到问题，请重试。如问题持续，请联系管理员
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}

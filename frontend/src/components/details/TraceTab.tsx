import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { getRunTrace } from '@/lib/api'

type TraceStep = Record<string, unknown>

interface TraceTabProps {
  runId: string | null
}

function stringValue(step: TraceStep, key: string, fallback = '-') {
  const value = step[key]
  return value === null || value === undefined || value === '' ? fallback : String(value)
}

function statusVariant(status: string) {
  if (status === 'completed') return 'success'
  if (status === 'failed' || status === 'error') return 'destructive'
  if (status === 'interrupted' || status === 'waiting_approval') return 'warning'
  return 'outline'
}

export function TraceTab({ runId }: TraceTabProps) {
  const [steps, setSteps] = useState<TraceStep[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) {
      setSteps([])
      return
    }

    let cancelled = false
    void getRunTrace(runId).then((result) => {
      if (cancelled) return
      if (!result.success) {
        setError(result.error?.message ?? 'Trace 加载失败')
        return
      }
      setSteps((result.data.steps ?? []) as TraceStep[])
      setError(null)
    })

    return () => {
      cancelled = true
    }
  }, [runId])

  if (!runId) {
    return (
      <div className="rounded-md border border-dashed border-border p-4 text-body text-muted-foreground">
        执行完成后可查看详细追踪信息
      </div>
    )
  }

  if (error) {
    return <div className="rounded-md border border-destructive/40 p-4 text-body">{error}</div>
  }

  if (steps.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-4 text-body text-muted-foreground">
        执行完成后可查看详细追踪信息
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {steps.map((step, index) => {
        const status = stringValue(step, 'status')
        const errorMessage = stringValue(step, 'error_message', '')
        const errorCode = stringValue(step, 'error_code', '')
        return (
          <Card
            key={`${stringValue(step, 'node_name', stringValue(step, 'node', 'step'))}-${index}`}
            className={errorMessage ? 'border-l-4 border-l-destructive' : ''}
          >
            <CardContent>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-body font-semibold">
                    {stringValue(step, 'node_name', stringValue(step, 'node', 'unknown_node'))}
                  </p>
                  <p className="mt-1 text-label text-muted-foreground">
                    tool_name: {stringValue(step, 'tool_name')} · latency_ms: {stringValue(step, 'latency_ms')}
                  </p>
                </div>
                <Badge variant={statusVariant(status)}>{status}</Badge>
              </div>
              {errorMessage ? (
                <div className="mt-3 rounded-md bg-destructive/10 p-2 text-label">
                  <span className="text-muted-foreground">error_code:</span> {errorCode || 'UNKNOWN'}
                  <br />
                  <span className="text-muted-foreground">error_message:</span> {errorMessage}
                </div>
              ) : null}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

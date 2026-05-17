import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getRunEvidence } from '@/lib/api'

interface EvidenceItem {
  doc_key?: string
  doc_id?: string
  chunk_id?: string
  title?: string
  section_title?: string
  excerpt?: string
  content?: string
  confidence?: number
  score?: number
  risk_level?: string
}

interface EvidenceTabProps {
  runId: string | null
}

function confidenceLabel(evidence: EvidenceItem) {
  const value = evidence.confidence ?? evidence.score
  if (typeof value !== 'number') return 'confidence n/a'
  return `${Math.round(value * 100)}%`
}

export function EvidenceTab({ runId }: EvidenceTabProps) {
  const [evidence, setEvidence] = useState<EvidenceItem[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) {
      setEvidence([])
      return
    }

    let cancelled = false
    void getRunEvidence(runId).then((result) => {
      if (cancelled) return
      if (!result.success) {
        setError(result.error?.message ?? '证据加载失败')
        return
      }
      setEvidence(result.data.evidence as EvidenceItem[])
      setError(null)
    })

    return () => {
      cancelled = true
    }
  }, [runId])

  if (!runId) {
    return (
      <div className="rounded-md border border-dashed border-border p-4 text-body text-muted-foreground">
        暂无证据
        <p className="mt-2 text-label">Agent 执行过程中将自动检索相关规则和证据</p>
      </div>
    )
  }

  if (error) {
    return <div className="rounded-md border border-destructive/40 p-4 text-body">{error}</div>
  }

  if (evidence.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-4 text-body text-muted-foreground">
        暂无证据
        <p className="mt-2 text-label">Agent 执行过程中将自动检索相关规则和证据</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {evidence.map((item, index) => (
        <Card key={`${item.doc_key ?? item.doc_id ?? 'evidence'}-${item.chunk_id ?? index}`}>
          <CardHeader className="flex flex-row items-start justify-between gap-3">
            <CardTitle className="min-w-0 truncate">{item.title ?? item.section_title ?? '规则证据'}</CardTitle>
            <Badge variant="outline">{confidenceLabel(item)}</Badge>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2 text-label text-muted-foreground">
              <span>{item.doc_key ?? item.doc_id ?? 'unknown_doc'}</span>
              {item.chunk_id ? <span>chunk {item.chunk_id}</span> : null}
              {item.risk_level ? <Badge variant="warning">{item.risk_level}</Badge> : null}
            </div>
            {(item.excerpt ?? item.content) ? (
              <p className="mt-3 line-clamp-4 text-body text-muted-foreground">{item.excerpt ?? item.content}</p>
            ) : null}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

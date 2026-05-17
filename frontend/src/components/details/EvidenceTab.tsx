import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) {
      return
    }

    let cancelled = false
    void getRunEvidence(runId)
      .then((result) => {
        if (cancelled) return
        if (!result.success) {
          setError(result.error?.message ?? '证据加载失败')
          return
        }
        setEvidence(result.data.evidence as EvidenceItem[])
        setExpandedKey(null)
        setError(null)
      })
      .catch(() => {
        if (!cancelled) {
          setError('证据加载失败')
        }
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
      {evidence.map((item, index) => {
        const itemKey = `${item.doc_key ?? item.doc_id ?? 'evidence'}-${item.chunk_id ?? index}`
        const expanded = expandedKey === itemKey
        const body = item.excerpt ?? item.content

        return (
          <Card key={itemKey}>
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
              {body ? (
                <p className={expanded ? 'mt-3 whitespace-pre-wrap text-body text-muted-foreground' : 'mt-3 line-clamp-4 text-body text-muted-foreground'}>
                  {body}
                </p>
              ) : (
                <p className="mt-3 text-body text-muted-foreground">该证据仅包含来源引用，未返回正文片段。</p>
              )}
              <Button
                type="button"
                variant="ghost"
                className="mt-3 h-8 gap-2 px-2 text-label"
                onClick={() => setExpandedKey(expanded ? null : itemKey)}
              >
                {expanded ? <ChevronDown className="h-4 w-4" aria-hidden="true" /> : <ChevronRight className="h-4 w-4" aria-hidden="true" />}
                {expanded ? '收起详情' : '查看详情'}
              </Button>
              {expanded ? (
                <dl className="mt-3 grid gap-2 border-t border-border pt-3 text-label">
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">doc</dt>
                    <dd className="min-w-0 truncate text-right">{item.doc_key ?? item.doc_id ?? 'unknown_doc'}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">chunk</dt>
                    <dd className="min-w-0 truncate text-right">{item.chunk_id ?? '-'}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">confidence</dt>
                    <dd>{confidenceLabel(item)}</dd>
                  </div>
                </dl>
              ) : null}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

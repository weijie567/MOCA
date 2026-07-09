import { ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { BusinessQueryOperation, BusinessQueryPayload, BusinessQueryRow, BusinessQueryRowValue, SseEvent } from '@/types/events'

interface BusinessQueryResultTabProps {
  steps: SseEvent[]
}

const EMPTY_TITLE = '暂无业务查询结果'
const EMPTY_BODY = '业务查询完成后，将在这里显示安全投影后的汇总、列表、详情、分组或对比结果。'
const DENIED_COPY = '当前权限范围内无法提供该业务数据。'
const EMPTY_RESULT_COPY = '当前权限范围和筛选条件下没有可显示的结果。'
const OPERATIONS = new Set<string>(['aggregate', 'list', 'detail', 'breakdown', 'compare'])
const UNSAFE_KEY_PARTS = [
  'raw',
  'sql',
  'tenant',
  'merchant_scope',
  'prompt',
  'tool_arg',
  'routing',
  'stack',
  'cursor_token',
]
const UNSAFE_DISPLAY_TEXT_PARTS = [
  'raw',
  'cursor-',
  'tenant',
  'merchant',
  'ord-secret',
  'secret-denied',
  'should-not-leak',
]

function text(value: unknown) {
  if (typeof value !== 'string') return ''
  const trimmed = value.trim()
  const normalized = trimmed.toLowerCase()
  if (UNSAFE_DISPLAY_TEXT_PARTS.some((part) => normalized.includes(part))) return ''
  return trimmed
}

function latestBusinessQuery(steps: SseEvent[]) {
  for (const step of [...steps].reverse()) {
    const query = step.payload?.business_query
    if (query && typeof query === 'object') return query
  }
  return null
}

function operationOf(query: BusinessQueryPayload | null): BusinessQueryOperation | null {
  const operation = text(query?.operation)
  return OPERATIONS.has(operation) ? (operation as BusinessQueryOperation) : null
}

function isUnsafeKey(key: string) {
  const normalized = key.toLowerCase()
  return UNSAFE_KEY_PARTS.some((part) => normalized.includes(part))
}

function valueLabel(value: BusinessQueryRowValue) {
  if (value === null) return '-'
  return String(value)
}

function safeRowEntries(row: BusinessQueryRow) {
  return Object.entries(row)
    .filter(([key, value]) => !isUnsafeKey(key) && (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' || value === null))
    .map(([key, value]) => [key, valueLabel(value)] as const)
}

function safeRows(query: BusinessQueryPayload) {
  return (Array.isArray(query.rows) ? query.rows : [])
    .map((row) => (row && typeof row === 'object' ? safeRowEntries(row).slice(0, 5) : []))
    .filter((row) => row.length > 0)
    .slice(0, 20)
}

function countLabel(query: BusinessQueryPayload) {
  const rowCount = typeof query.row_count === 'number' ? query.row_count : null
  const limit = typeof query.limit === 'number' ? query.limit : null
  if (rowCount !== null && limit !== null) return `${rowCount}/${limit}`
  if (rowCount !== null) return String(rowCount)
  return null
}

function EmptyState({ copy = EMPTY_BODY }: { copy?: string }) {
  return (
    <div className="rounded-md border border-dashed border-border p-4 text-body text-muted-foreground">
      <p className="font-semibold text-foreground">{EMPTY_TITLE}</p>
      <p className="mt-2 text-label">{copy}</p>
    </div>
  )
}

function StateMessage({ variant, children }: { variant: 'warning' | 'empty'; children: string }) {
  return (
    <div
      className={
        variant === 'warning'
          ? 'rounded-md border border-status-waiting/40 bg-status-waiting/10 p-4 text-body'
          : 'rounded-md border border-dashed border-border p-4 text-body text-muted-foreground'
      }
    >
      {children}
    </div>
  )
}

function ResultHeader({ query, operation }: { query: BusinessQueryPayload; operation: BusinessQueryOperation }) {
  const title = text(query.result_label) || text(query.resource_label) || '业务查询结果'
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
      <div className="min-w-0">
        <p className="text-heading font-semibold">{title}</p>
        <p className="mt-1 text-label text-muted-foreground">{text(query.resource_label) || operation}</p>
      </div>
      <Badge variant="outline">{operation}</Badge>
    </div>
  )
}

function Metadata({ query }: { query: BusinessQueryPayload }) {
  const items = [
    ['范围', text(query.scope_label)],
    ['时间', text(query.time_label)],
    ['筛选', text(query.filters_label)],
    ['新鲜度', text(query.freshness_label)],
    ['字段', text(query.fields_label)],
    ['分组', text(query.group_by_label)],
    ['对比', text(query.compare_label)],
  ].filter(([, value]) => value)

  if (items.length === 0) return null

  return (
    <dl className="grid gap-2 rounded-md border border-border bg-muted/20 p-3 text-label sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={label} className="grid grid-cols-[64px_1fr] gap-2">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function QueryActions({ query }: { query: BusinessQueryPayload }) {
  const cursorLabel = text(query.cursor_label)
  const canDrillDown = Array.isArray(query.allowed_drilldowns) && query.allowed_drilldowns.length > 0
  if (!cursorLabel && !canDrillDown) return null

  return (
    <div className="flex flex-wrap gap-2 border-t border-border pt-3">
      {cursorLabel ? (
        <Button type="button" variant="outline" className="h-8 gap-2 px-2 text-label">
          {cursorLabel}
        </Button>
      ) : null}
      {canDrillDown ? (
        <Button type="button" variant="ghost" className="h-8 gap-2 px-2 text-label">
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
          查看详情
        </Button>
      ) : null}
    </div>
  )
}

function RowsTable({ rows }: { rows: Array<ReadonlyArray<readonly [string, string]>> }) {
  if (rows.length === 0) return null
  const headers = rows[0].map(([key]) => key)

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full table-fixed text-left text-label">
        <thead className="bg-muted/40 text-muted-foreground">
          <tr>
            {headers.map((header) => (
              <th key={header} className="px-3 py-2 font-normal">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-t border-border">
              {headers.map((header) => {
                const value = row.find(([key]) => key === header)?.[1] ?? '-'
                return (
                  <td key={header} className="min-w-0 break-words px-3 py-2 text-body">
                    {value}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DefinitionList({ rows }: { rows: Array<ReadonlyArray<readonly [string, string]>> }) {
  const entries = rows[0] ?? []
  if (entries.length === 0) return null

  return (
    <dl className="grid gap-2 rounded-md border border-border p-3 text-body sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="grid grid-cols-[88px_1fr] gap-3">
          <dt className="text-label text-muted-foreground">{key}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function AggregateView({ query }: { query: BusinessQueryPayload }) {
  return (
    <div className="space-y-3">
      <Metadata query={query} />
    </div>
  )
}

function ListView({ query, rows }: { query: BusinessQueryPayload; rows: Array<ReadonlyArray<readonly [string, string]>> }) {
  const count = countLabel(query)
  return (
    <div className="space-y-3">
      {count ? <p className="text-label text-muted-foreground">rows: {count}</p> : null}
      <Metadata query={query} />
      <RowsTable rows={rows} />
      <QueryActions query={query} />
    </div>
  )
}

function OperationView({
  operation,
  query,
  rows,
}: {
  operation: BusinessQueryOperation
  query: BusinessQueryPayload
  rows: Array<ReadonlyArray<readonly [string, string]>>
}) {
  if (operation === 'aggregate') return <AggregateView query={query} />
  if (operation === 'detail') return <DefinitionList rows={rows} />
  return <ListView query={query} rows={rows} />
}

export function BusinessQueryResultTab({ steps }: BusinessQueryResultTabProps) {
  const query = latestBusinessQuery(steps)
  const operation = operationOf(query)
  if (!query || !operation) return <EmptyState />

  if (query.safe_reason === 'scope_denied_no_existence_leak') {
    return <StateMessage variant="warning">{DENIED_COPY}</StateMessage>
  }
  if (query.safe_reason === 'empty_result') {
    return <StateMessage variant="empty">{EMPTY_RESULT_COPY}</StateMessage>
  }

  const rows = safeRows(query)
  if (operation !== 'aggregate' && rows.length === 0 && (query.row_count ?? null) === 0) {
    return <StateMessage variant="empty">{EMPTY_RESULT_COPY}</StateMessage>
  }

  return (
    <div className="space-y-3">
      <ResultHeader query={query} operation={operation} />
      <OperationView operation={operation} query={query} rows={rows} />
    </div>
  )
}

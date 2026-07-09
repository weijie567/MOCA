import { render, screen } from '@testing-library/react'
import { createElement } from 'react'
import { describe, expect, it } from 'vitest'
import { BusinessQueryResultTab } from './BusinessQueryResultTab'
import type { SseEvent } from '@/types/events'

function businessQueryStep(payload: SseEvent['payload']): SseEvent {
  return {
    event_type: 'final_response',
    run_id: 'run-business-query',
    step_index: 1,
    node_name: 'final_response',
    status: 'completed',
    message: '业务查询结果',
    timestamp: '2026-07-09T12:00:00.000Z',
    payload,
  }
}

describe('BusinessQueryResultTab', () => {
  it('does not render unsafe display labels from business query payloads', () => {
    render(
      createElement(BusinessQueryResultTab, {
        steps: [
          businessQueryStep({
            business_query: {
              operation: 'list',
              resource_label: 'MERCHANT-SECRET',
              result_label: 'ORD-SECRET-DENIED',
              scope_label: 'tenant-001',
              time_label: '本周',
              filters_label: 'raw filter payload',
              freshness_label: '当前可用业务数据',
              fields_label: 'cursor-raw-should-not-leak',
              safe_reason: 'ok',
              rows: [{ order_no: 'ORD-BQ-001', status: 'paid' }],
              row_count: 1,
              limit: 20,
              cursor_label: 'cursor-raw-should-not-leak',
              allowed_drilldowns: [],
              group_by_label: 'raw group',
              compare_label: 'ORD-SECRET-DENIED',
            },
          }),
        ],
      }),
    )

    expect(screen.getByText('业务查询结果')).toBeTruthy()
    expect(screen.getByText('本周')).toBeTruthy()
    expect(screen.getByText('当前可用业务数据')).toBeTruthy()
    expect(screen.getByText('ORD-BQ-001')).toBeTruthy()

    for (const forbidden of [
      'MERCHANT-SECRET',
      'ORD-SECRET-DENIED',
      'tenant-001',
      'raw filter payload',
      'cursor-raw-should-not-leak',
      'raw group',
    ]) {
      expect(screen.queryByText(forbidden)).toBeNull()
    }
  })
})

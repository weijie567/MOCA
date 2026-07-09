import { act, render, renderHook, screen } from '@testing-library/react'
import { createElement } from 'react'
import { DetailsPanel } from '@/components/details/DetailsPanel'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TimelineStep } from '@/components/timeline/TimelineStep'
import { createRun } from '@/lib/api'
import { connectToRunEvents } from '@/lib/sse'
import type { SseEvent } from '@/types/events'
import { useAgentRun } from './useAgentRun'

vi.mock('@/lib/api', () => ({
  createRun: vi.fn(),
  decideApproval: vi.fn(),
  getPendingApprovals: vi.fn().mockResolvedValue({ success: true, data: { approvals: [], total: 0 } }),
  getRunEvidence: vi.fn().mockResolvedValue({ success: true, data: { evidence: [] } }),
  getRunStatus: vi.fn(),
  getRunTrace: vi.fn().mockResolvedValue({ success: true, data: { run_id: 'run-1', steps: [], timeline: [] } }),
}))

vi.mock('@/lib/sse', () => ({
  connectToRunEvents: vi.fn(),
}))

const createRunMock = vi.mocked(createRun)
const connectToRunEventsMock = vi.mocked(connectToRunEvents)
let streamCallbacks: Map<string, Parameters<typeof connectToRunEvents>[1]>

function createMemoryStorage(): Storage {
  const items = new Map<string, string>()

  return {
    get length() {
      return items.size
    },
    clear() {
      items.clear()
    },
    getItem(key: string) {
      return items.get(key) ?? null
    },
    key(index: number) {
      return Array.from(items.keys())[index] ?? null
    },
    removeItem(key: string) {
      items.delete(key)
    },
    setItem(key: string, value: string) {
      items.set(key, value)
    },
  }
}

describe('useAgentRun thread lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    streamCallbacks = new Map()
    Object.defineProperty(window, 'localStorage', {
      value: createMemoryStorage(),
      configurable: true,
    })
    window.localStorage.clear()
    vi.stubGlobal('crypto', {
      randomUUID: vi
        .fn()
        .mockReturnValueOnce('thread-1')
        .mockReturnValueOnce('thread-2')
        .mockReturnValue('thread-next'),
    })
    createRunMock.mockResolvedValue({
      success: true,
      data: { run_id: 'run-1', status: 'running' },
    })
    connectToRunEventsMock.mockImplementation((runId, callbacks) => {
      streamCallbacks.set(runId, callbacks)
      return new AbortController()
    })
  })

  it('reuses one thread id for consecutive submits in the same conversation', async () => {
    const { result } = renderHook(() => useAgentRun())

    await act(async () => {
      await result.current.submitQuery('first question')
    })
    await act(async () => {
      await result.current.submitQuery('second question')
    })

    expect(createRunMock).toHaveBeenCalledTimes(2)
    expect(createRunMock.mock.calls[0][1]).toBe('demo-thread-1')
    expect(createRunMock.mock.calls[1][1]).toBe('demo-thread-1')
  })

  it('uses a new thread id after starting a new conversation', async () => {
    const { result } = renderHook(() => useAgentRun())

    await act(async () => {
      await result.current.submitQuery('first question')
    })
    act(() => {
      result.current.newConversation()
    })
    await act(async () => {
      await result.current.submitQuery('new conversation question')
    })

    expect(createRunMock).toHaveBeenCalledTimes(2)
    expect(createRunMock.mock.calls[0][1]).toBe('demo-thread-1')
    expect(createRunMock.mock.calls[1][1]).toBe('demo-thread-2')
  })

  it('keeps the current thread id after remounting from local storage', async () => {
    const firstHook = renderHook(() => useAgentRun())

    await act(async () => {
      await firstHook.result.current.submitQuery('first question')
    })
    firstHook.unmount()

    const secondHook = renderHook(() => useAgentRun())
    await act(async () => {
      await secondHook.result.current.submitQuery('after refresh question')
    })

    expect(createRunMock).toHaveBeenCalledTimes(2)
    expect(createRunMock.mock.calls[0][1]).toBe('demo-thread-1')
    expect(createRunMock.mock.calls[1][1]).toBe('demo-thread-1')
  })

  it('keeps earlier agent replies when a new query starts in the same conversation', async () => {
    createRunMock
      .mockResolvedValueOnce({ success: true, data: { run_id: 'run-1', status: 'pending' } })
      .mockResolvedValueOnce({ success: true, data: { run_id: 'run-2', status: 'pending' } })
    const { result } = renderHook(() => useAgentRun())

    await act(async () => {
      await result.current.submitQuery('first question')
    })
    act(() => {
      streamCallbacks.get('run-1')?.onEvent(
        event({
          event_type: 'final_response',
          run_id: 'run-1',
          step_index: 1,
          node_name: null,
          status: 'completed',
          message: '已完成',
          payload: { final_response: 'first answer' },
        }),
      )
    })
    await act(async () => {
      await result.current.submitQuery('second question')
    })

    expect(result.current.state.messages).toMatchObject([
      { role: 'user', content: 'first question', status: 'completed' },
      { role: 'assistant', content: 'first answer', status: 'completed' },
      { role: 'user', content: 'second question', status: 'completed' },
      { role: 'assistant', content: '', status: 'pending' },
    ])
  })

  it('ignores stale terminal-run events after a new query has reset active steps', async () => {
    let resolveSecondRun: ((value: Awaited<ReturnType<typeof createRun>>) => void) | null = null
    createRunMock
      .mockResolvedValueOnce({ success: true, data: { run_id: 'run-1', status: 'pending' } })
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveSecondRun = resolve
        }),
      )
    const { result } = renderHook(() => useAgentRun())

    await act(async () => {
      await result.current.submitQuery('当前有多少订单')
    })
    act(() => {
      streamCallbacks.get('run-1')?.onEvent(
        event({
          event_type: 'final_response',
          run_id: 'run-1',
          step_index: 1,
          node_name: 'final_response',
          status: 'completed',
          message: '需要补充信息',
          payload: {
            response_kind: 'clarification',
            safe_reason: 'missing_time_range',
            final_response: '要统计该指标，请选择时间范围。',
          },
        }),
      )
    })

    let secondSubmit: Promise<void> | null = null
    act(() => {
      secondSubmit = result.current.submitQuery('今天有多少退款单') as Promise<void>
    })
    expect(result.current.state.steps).toEqual([])

    act(() => {
      streamCallbacks.get('run-1')?.onEvent(
        event({
          event_type: 'step_completed',
          run_id: 'run-1',
          step_index: 2,
          node_name: 'investigate',
          status: 'completed',
          message: '正在调查订单和规则',
          payload: { tool_name: 'query_business_metric' },
        }),
      )
    })

    expect(result.current.state.steps).toEqual([])
    expect(result.current.state.messages).toMatchObject([
      { role: 'user', content: '当前有多少订单', status: 'completed' },
      { role: 'assistant', content: '要统计该指标，请选择时间范围。', status: 'completed' },
      { role: 'user', content: '今天有多少退款单', status: 'completed' },
      { role: 'assistant', content: '', status: 'pending' },
    ])

    await act(async () => {
      resolveSecondRun?.({ success: true, data: { run_id: 'run-2', status: 'pending' } })
      await secondSubmit
    })

    expect(result.current.state.runId).toBe('run-2')
    expect(result.current.state.steps).toEqual([])
  })

  it('keeps typed business query payloads on the active run but ignores stale business query callbacks', async () => {
    let resolveSecondRun: ((value: Awaited<ReturnType<typeof createRun>>) => void) | null = null
    createRunMock
      .mockResolvedValueOnce({ success: true, data: { run_id: 'run-1', status: 'pending' } })
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveSecondRun = resolve
        }),
      )
    const { result } = renderHook(() => useAgentRun())

    await act(async () => {
      await result.current.submitQuery('本周多少订单')
    })
    act(() => {
      streamCallbacks.get('run-1')?.onEvent(
        event({
          event_type: 'final_response',
          run_id: 'run-1',
          step_index: 1,
          node_name: 'final_response',
          status: 'completed',
          message: '业务汇总查询完成',
          payload: {
            response_kind: 'business_query_answer',
            final_response: '本周订单 128 单。',
            business_query: {
              operation: 'aggregate',
              resource_label: '订单',
              result_label: '本周订单 128 单',
              scope_label: '当前权限范围',
              time_label: '本周',
            },
          } as unknown as SseEvent['payload'],
        }),
      )
    })

    expect(result.current.state.steps[0].payload).toMatchObject({
      response_kind: 'business_query_answer',
      business_query: {
        operation: 'aggregate',
        result_label: '本周订单 128 单',
      },
    })

    let secondSubmit: Promise<void> | null = null
    act(() => {
      secondSubmit = result.current.submitQuery('订单号是多少') as Promise<void>
    })
    expect(result.current.state.steps).toEqual([])

    act(() => {
      streamCallbacks.get('run-1')?.onEvent(
        event({
          event_type: 'final_response',
          run_id: 'run-1',
          step_index: 2,
          node_name: 'final_response',
          status: 'completed',
          message: '业务列表查询完成',
          payload: {
            response_kind: 'business_query_answer',
            final_response: '旧结果不应回填。',
            business_query: {
              operation: 'list',
              resource_label: '订单',
              result_label: '旧列表',
              row_count: 2,
              limit: 20,
              rows: [{ 订单号: 'ORD-STALE' }],
            },
          } as unknown as SseEvent['payload'],
        }),
      )
    })

    expect(result.current.state.steps).toEqual([])

    await act(async () => {
      resolveSecondRun?.({ success: true, data: { run_id: 'run-2', status: 'pending' } })
      await secondSubmit
    })

    expect(result.current.state.runId).toBe('run-2')
    expect(result.current.state.steps).toEqual([])
  })

  it('updates one timeline row per node instead of appending running and completed duplicates', async () => {
    createRunMock.mockResolvedValueOnce({ success: true, data: { run_id: 'run-1', status: 'pending' } })
    const { result } = renderHook(() => useAgentRun())

    await act(async () => {
      await result.current.submitQuery('check refund status')
    })
    const callbacks = streamCallbacks.get('run-1')

    act(() => {
      callbacks?.onEvent(
        event({
          event_type: 'run_started',
          run_id: 'run-1',
          step_index: 0,
          node_name: null,
          status: 'running',
          message: '正在接收请求',
        }),
      )
      callbacks?.onEvent(
        event({
          event_type: 'step_started',
          run_id: 'run-1',
          step_index: 1,
          node_name: 'receive_request',
          status: 'running',
          message: '正在接收请求',
        }),
      )
    })

    expect(result.current.state.steps).toHaveLength(1)
    expect(result.current.state.steps[0]).toMatchObject({
      node_name: 'receive_request',
      status: 'running',
    })

    act(() => {
      callbacks?.onEvent(
        event({
          event_type: 'step_completed',
          run_id: 'run-1',
          step_index: 1,
          node_name: 'receive_request',
          status: 'completed',
          message: '正在接收请求',
        }),
      )
      callbacks?.onEvent(
        event({
          event_type: 'step_started',
          run_id: 'run-1',
          step_index: 2,
          node_name: 'final_response',
          status: 'running',
          message: '已完成',
        }),
      )
      callbacks?.onEvent(
        event({
          event_type: 'step_completed',
          run_id: 'run-1',
          step_index: 2,
          node_name: 'final_response',
          status: 'completed',
          message: '已完成',
        }),
      )
      callbacks?.onEvent(
        event({
          event_type: 'final_response',
          run_id: 'run-1',
          step_index: 3,
          node_name: null,
          status: 'completed',
          message: '已完成',
          payload: { final_response: 'done' },
        }),
      )
    })

    expect(result.current.state.steps).toHaveLength(2)
    expect(result.current.state.steps.map((step) => step.node_name)).toEqual(['receive_request', 'final_response'])
    expect(result.current.state.steps.map((step) => step.status)).toEqual(['completed', 'completed'])
    expect(result.current.state.status).toBe('completed')
    expect(result.current.state.messages[1]).toMatchObject({
      role: 'assistant',
      content: 'done',
      status: 'completed',
    })
  })
})

describe('TimelineStep safe result labels', () => {
  it('renders direct response, clarification, unsupported, metric, RAG, and tool labels from safe payloads', () => {
    const cases: Array<{ event: SseEvent; expected: string[]; forbidden?: string[] }> = [
      {
        event: event({
          event_type: 'final_response',
          node_name: 'final_response',
          status: 'completed',
          payload: { response_kind: 'small_talk' },
        }),
        expected: ['直接回复', 'response: direct'],
      },
      {
        event: event({
          event_type: 'final_response',
          node_name: 'final_response',
          status: 'completed',
          payload: { response_kind: 'clarification', safe_reason: 'missing_time_range' },
        }),
        expected: ['需要补充信息', '原因: 缺少时间范围'],
      },
      {
        event: event({
          event_type: 'final_response',
          node_name: 'final_response',
          status: 'completed',
          payload: { response_kind: 'unsupported', safe_reason: 'unsupported_metric' },
        }),
        expected: ['当前能力不支持', '原因: 不支持的统计口径'],
      },
      {
        event: event({
          event_type: 'step_started',
          node_name: 'investigate',
          status: 'running',
          payload: {
            response_kind: 'metric_answer',
            metric_id: 'refund_case_count',
            scope_label: '当前权限范围',
          },
        }),
        expected: ['正在查询业务指标', 'metric: refund_case_count · scope: 当前权限范围'],
      },
      {
        event: event({
          event_type: 'final_response',
          node_name: 'final_response',
          status: 'completed',
          payload: {
            response_kind: 'metric_answer',
            metric: {
              metric_id: 'refund_case_count',
              metric_label: '退款单数',
              scope_label: '当前权限范围',
              safe_reason: 'ok',
            },
            routing_hints: { route: 'SHOULD_NOT_RENDER' },
          } as unknown as SseEvent['payload'],
        }),
        expected: ['业务指标查询完成', 'metric: 退款单数 · scope: 当前权限范围'],
        forbidden: ['routing_hints', 'SHOULD_NOT_RENDER'],
      },
      {
        event: event({
          event_type: 'step_started',
          node_name: 'rag_context_build',
          status: 'running',
          payload: { evidence_count: 2 },
        }),
        expected: ['正在构建证据上下文', 'evidence: 2'],
      },
      {
        event: event({
          event_type: 'step_completed',
          node_name: 'investigate',
          status: 'completed',
          payload: {
            tool_name: 'query_business_metric',
            tool_label: '查询业务指标',
            raw_args: { merchant_id: 'MERCHANT-SHOULD-NOT-LEAK' },
          } as unknown as SseEvent['payload'],
        }),
        expected: ['查询业务指标', 'tool: 查询业务指标'],
        forbidden: ['MERCHANT-SHOULD-NOT-LEAK', 'raw_args'],
      },
    ]

    cases.forEach(({ event: step, expected, forbidden = [] }) => {
      const { unmount } = render(createElement(TimelineStep, { step, isLast: true }))

      expected.forEach((text) => expect(screen.getByText(text)).toBeTruthy())
      forbidden.forEach((text) => expect(screen.queryByText(text)).toBeNull())

      unmount()
    })
  })

  it('renders business query timeline labels from typed safe payload fields only', () => {
    const cases: Array<{ event: SseEvent; expected: string[]; forbidden?: string[] }> = [
      {
        event: event({
          event_type: 'step_started',
          node_name: 'investigate',
          status: 'running',
          payload: {
            response_kind: 'business_query_answer',
            business_query: {
              operation: 'aggregate',
              resource_label: '订单',
              result_label: '本周订单 128 单',
              scope_label: '当前权限范围',
              raw_sql: 'SHOULD_NOT_RENDER',
            },
            raw_args: { tenant_id: 'tenant-secret' },
          } as unknown as SseEvent['payload'],
        }),
        expected: ['正在查询业务汇总', 'aggregate: 本周订单 128 单 · scope: 当前权限范围'],
        forbidden: ['raw_args', 'tenant-secret', 'raw_sql', 'SHOULD_NOT_RENDER'],
      },
      {
        event: event({
          event_type: 'final_response',
          node_name: 'final_response',
          status: 'completed',
          payload: {
            response_kind: 'business_query_answer',
            business_query: {
              operation: 'aggregate',
              resource_label: '订单',
              result_label: '本周订单 128 单',
              scope_label: '当前权限范围',
            },
          } as unknown as SseEvent['payload'],
        }),
        expected: ['业务汇总查询完成', 'aggregate: 本周订单 128 单 · scope: 当前权限范围'],
      },
      {
        event: event({
          event_type: 'final_response',
          node_name: 'final_response',
          status: 'completed',
          payload: {
            response_kind: 'business_query_answer',
            business_query: {
              operation: 'list',
              resource_label: '订单',
              row_count: 5,
              limit: 20,
              rows: [{ 订单号: 'ORD-SAFE-1' }],
              raw_payload: 'SHOULD_NOT_RENDER',
              cursor_label: '查看更多',
            },
            raw_cursor: 'cursor-secret',
          } as unknown as SseEvent['payload'],
        }),
        expected: ['业务列表查询完成', 'list: 订单 · rows: 5/20'],
        forbidden: ['ORD-SAFE-1', 'raw_payload', 'raw_cursor', 'cursor-secret'],
      },
      {
        event: event({
          event_type: 'final_response',
          node_name: 'final_response',
          status: 'completed',
          payload: {
            response_kind: 'business_query_answer',
            business_query: {
              operation: 'detail',
              resource_label: '退款单',
              fields_label: '退款单号、状态、金额',
              merchant_scope: ['merchant-secret'],
            },
            routing_hints: { route: 'SHOULD_NOT_RENDER' },
          } as unknown as SseEvent['payload'],
        }),
        expected: ['业务详情查询完成', 'detail: 退款单 · fields: 退款单号、状态、金额'],
        forbidden: ['routing_hints', 'merchant-secret', 'merchant_scope', 'SHOULD_NOT_RENDER'],
      },
      {
        event: event({
          event_type: 'final_response',
          node_name: 'final_response',
          status: 'completed',
          payload: {
            response_kind: 'business_query_answer',
            business_query: {
              operation: 'breakdown',
              resource_label: '订单',
              group_by_label: '订单状态',
            },
          } as unknown as SseEvent['payload'],
        }),
        expected: ['业务分组查询完成', 'breakdown: 订单 · by: 订单状态'],
      },
      {
        event: event({
          event_type: 'final_response',
          node_name: 'final_response',
          status: 'completed',
          payload: {
            response_kind: 'business_query_answer',
            business_query: {
              operation: 'compare',
              result_label: '订单量对比',
              compare_label: '本周 vs 上周',
            },
          } as unknown as SseEvent['payload'],
        }),
        expected: ['业务对比查询完成', 'compare: 订单量对比 · 本周 vs 上周'],
      },
    ]

    cases.forEach(({ event: step, expected, forbidden = [] }) => {
      const { unmount } = render(createElement(TimelineStep, { step, isLast: true }))

      expected.forEach((text) => expect(screen.getByText(text)).toBeTruthy())
      forbidden.forEach((text) => expect(screen.queryByText(text)).toBeNull())

      unmount()
    })
  })
})

describe('DetailsPanel business query Result tab', () => {
  it('puts Result first and renders aggregate, list, detail, breakdown, and compare safely', () => {
    const cases: Array<{ step: SseEvent; expected: string[]; forbidden?: string[] }> = [
      {
        step: businessQueryStep({
          operation: 'aggregate',
          resource_label: '订单',
          result_label: '本周订单 128 单',
          scope_label: '当前权限范围',
          time_label: '本周',
          filters_label: '无',
          freshness_label: '当前可用业务数据',
          raw_sql: 'SHOULD_NOT_RENDER',
        }),
        expected: ['本周订单 128 单', '当前权限范围', '本周', '当前可用业务数据'],
        forbidden: ['raw_sql', 'SHOULD_NOT_RENDER'],
      },
      {
        step: businessQueryStep({
          operation: 'list',
          resource_label: '订单',
          result_label: '订单列表',
          scope_label: '当前权限范围',
          row_count: 2,
          limit: 20,
          cursor_label: '查看更多',
          allowed_drilldowns: ['detail'],
          rows: [
            { 订单号: 'ORD-SAFE-1', 状态: '已支付', raw_payload: 'SHOULD_NOT_RENDER' },
            { 订单号: 'ORD-SAFE-2', 状态: '已完成', tenant_id: 'tenant-secret' },
          ],
          raw_cursor: 'cursor-secret',
        }),
        expected: ['订单列表', 'ORD-SAFE-1', 'ORD-SAFE-2', '查看更多', '查看详情'],
        forbidden: ['raw_payload', 'tenant-secret', 'raw_cursor', 'cursor-secret', 'SHOULD_NOT_RENDER'],
      },
      {
        step: businessQueryStep({
          operation: 'detail',
          resource_label: '退款单',
          result_label: '退款单详情',
          fields_label: '退款单号、状态、金额',
          rows: [{ 退款单号: 'RF-SAFE-1', 状态: '待处理', merchant_scope: 'merchant-secret' }],
        }),
        expected: ['退款单详情', 'RF-SAFE-1', '待处理'],
        forbidden: ['merchant_scope', 'merchant-secret'],
      },
      {
        step: businessQueryStep({
          operation: 'breakdown',
          resource_label: '订单',
          result_label: '订单状态分组',
          group_by_label: '订单状态',
          rows: [
            { 分组: '已支付', 数量: 8 },
            { 分组: '已完成', 数量: 12 },
          ],
        }),
        expected: ['订单状态分组', '订单状态', '已支付', '已完成'],
      },
      {
        step: businessQueryStep({
          operation: 'compare',
          resource_label: '订单',
          result_label: '订单量对比',
          compare_label: '本周 vs 上周',
          rows: [
            { 对比项: '本周', 数量: 128, 变化: '+8%' },
            { 对比项: '上周', 数量: 118 },
          ],
        }),
        expected: ['订单量对比', '本周 vs 上周', '+8%'],
      },
    ]

    cases.forEach(({ step, expected, forbidden = [] }) => {
      const { unmount } = render(
        createElement(DetailsPanel, {
          runId: 'run-1',
          approvalId: null,
          role: 'support_agent',
          status: 'completed',
          steps: [step],
        }),
      )

      expect(screen.getAllByRole('button').slice(0, 5).map((button) => button.textContent)).toEqual([
        'Result',
        'Evidence',
        'Approval',
        'Trace',
        'Run Info',
      ])
      expected.forEach((text) => expect(screen.getByText(text)).toBeTruthy())
      forbidden.forEach((text) => expect(screen.queryByText(text)).toBeNull())

      unmount()
    })
  })

  it('renders denied, empty, missing, and malformed business query states without raw JSON fallback', () => {
    const cases: Array<{ step?: SseEvent; expected: string[]; forbidden?: string[] }> = [
      {
        step: businessQueryStep({
          operation: 'list',
          resource_label: '订单',
          safe_reason: 'scope_denied_no_existence_leak',
          rows: [],
          row_count: 0,
          raw_args: { merchant_id: 'MERCHANT-SECRET' },
        }),
        expected: ['当前权限范围内无法提供该业务数据。'],
        forbidden: ['MERCHANT-SECRET', 'raw_args'],
      },
      {
        step: businessQueryStep({
          operation: 'list',
          resource_label: '订单',
          safe_reason: 'empty_result',
          rows: [],
          row_count: 0,
        }),
        expected: ['当前权限范围和筛选条件下没有可显示的结果。'],
      },
      {
        expected: ['暂无业务查询结果', '业务查询完成后，将在这里显示安全投影后的汇总、列表、详情、分组或对比结果。'],
      },
      {
        step: businessQueryStep({
          operation: 'unknown',
          resource_label: '订单',
          result_label: '不能安全显示',
          rows: [{ raw_payload: 'SHOULD_NOT_RENDER', tool_args: 'secret' }],
        }),
        expected: ['暂无业务查询结果'],
        forbidden: ['不能安全显示', 'raw_payload', 'tool_args', 'SHOULD_NOT_RENDER'],
      },
    ]

    cases.forEach(({ step, expected, forbidden = [] }) => {
      const { unmount } = render(
        createElement(DetailsPanel, {
          runId: step ? 'run-1' : null,
          approvalId: null,
          role: 'support_agent',
          status: step ? 'completed' : 'idle',
          steps: step ? [step] : [],
        }),
      )

      expected.forEach((text) => expect(screen.getByText(text)).toBeTruthy())
      forbidden.forEach((text) => expect(screen.queryByText(text)).toBeNull())

      unmount()
    })
  })
})

function event(overrides: Partial<SseEvent>): SseEvent {
  return {
    event_type: 'step_started',
    run_id: 'run-1',
    step_index: 1,
    node_name: 'receive_request',
    status: 'running',
    message: '正在接收请求',
    timestamp: new Date().toISOString(),
    payload: {},
    ...overrides,
  }
}

function businessQueryStep(businessQuery: Record<string, unknown>): SseEvent {
  return event({
    event_type: 'final_response',
    run_id: 'run-1',
    step_index: 2,
    node_name: 'final_response',
    status: 'completed',
    message: '业务查询完成',
    payload: {
      response_kind: 'business_query_answer',
      final_response: '业务查询完成。',
      business_query: businessQuery,
      routing_hints: { route: 'SHOULD_NOT_RENDER' },
    } as unknown as SseEvent['payload'],
  })
}

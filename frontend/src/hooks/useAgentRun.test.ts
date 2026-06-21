import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRun } from '@/lib/api'
import { connectToRunEvents } from '@/lib/sse'
import type { SseEvent } from '@/types/events'
import { useAgentRun } from './useAgentRun'

vi.mock('@/lib/api', () => ({
  createRun: vi.fn(),
  decideApproval: vi.fn(),
  getRunStatus: vi.fn(),
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

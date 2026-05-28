import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRun } from '@/lib/api'
import { connectToRunEvents } from '@/lib/sse'
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
    connectToRunEventsMock.mockReturnValue(new AbortController())
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
})

import { fetchEventSource } from '@microsoft/fetch-event-source'
import { apiUrl, getAuthToken } from './api'
import type { SseEvent } from '@/types/events'

export interface SseCallbacks {
  onEvent: (event: SseEvent) => void
  onError: (error: Error) => void
  onClose: () => void
}

export function connectToRunEvents(runId: string, callbacks: SseCallbacks): AbortController {
  const controller = new AbortController()
  const token = getAuthToken()

  void fetchEventSource(apiUrl(`/agent-runs/${runId}/events`), {
    method: 'GET',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal: controller.signal,
    onmessage(message) {
      if (!message.data) return
      try {
        callbacks.onEvent(JSON.parse(message.data) as SseEvent)
      } catch {
        // Malformed events are ignored; the stream can continue with the next valid frame.
      }
    },
    onerror(error) {
      callbacks.onError(error instanceof Error ? error : new Error(String(error)))
      callbacks.onClose()
      throw error
    },
    onclose() {
      callbacks.onClose()
    },
  })

  return controller
}

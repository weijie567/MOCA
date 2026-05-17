import { useState } from 'react'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'

interface ChatPanelState {
  status: string
  finalResponse: string | null
  error: string | null
}

interface ChatPanelProps {
  state: ChatPanelState
  submitQuery: (query: string) => void | Promise<void>
}

function inputDisabled(status: string) {
  return status === 'running' || status === 'pending' || status === 'waiting_approval'
}

export function ChatPanel({ state, submitQuery }: ChatPanelProps) {
  const [queries, setQueries] = useState<string[]>([])

  async function handleSubmit(query: string) {
    setQueries((current) => [...current, query])
    await submitQuery(query)
  }

  return (
    <section className="flex min-h-0 flex-col border-r border-border bg-background">
      <div className="border-b border-border px-4 py-3">
        <h1 className="text-heading font-semibold">Chat</h1>
        <p className="mt-1 text-label text-muted-foreground">退款咨询与补偿请求入口</p>
      </div>
      <MessageList
        queries={queries}
        finalResponse={state.finalResponse}
        status={state.status}
        error={state.error}
      />
      <ChatInput disabled={inputDisabled(state.status)} onSubmit={handleSubmit} />
    </section>
  )
}

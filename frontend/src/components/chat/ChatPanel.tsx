import { useState } from 'react'
import { Plus } from 'lucide-react'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'
import { Button } from '@/components/ui/button'

interface ChatPanelState {
  status: string
  finalResponse: string | null
  error: string | null
}

interface ChatPanelProps {
  state: ChatPanelState
  submitQuery: (query: string) => void | Promise<void>
  newConversation: () => void
  authReady: boolean
  authError: string | null
}

function inputDisabled(status: string) {
  return status === 'running' || status === 'pending' || status === 'waiting_approval'
}

export function ChatPanel({ state, submitQuery, newConversation, authReady, authError }: ChatPanelProps) {
  const [queries, setQueries] = useState<string[]>([])

  async function handleSubmit(query: string) {
    setQueries((current) => [...current, query])
    await submitQuery(query)
  }

  function handleNewConversation() {
    setQueries([])
    newConversation()
  }

  return (
    <section className="flex min-h-0 min-w-0 flex-col border-r border-border bg-background">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <h1 className="text-heading font-semibold">Chat</h1>
          <p className="mt-1 text-label text-muted-foreground">退款咨询与补偿请求入口</p>
        </div>
        <Button
          className="h-8 shrink-0 gap-2 px-2.5 text-label"
          type="button"
          variant="outline"
          onClick={handleNewConversation}
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          新对话
        </Button>
      </div>
      <MessageList
        queries={queries}
        finalResponse={state.finalResponse}
        status={state.status}
        error={state.error}
      />
      {authError ? (
        <div
          className="border-t border-destructive/40 bg-destructive/10 px-4 py-3 text-label text-destructive"
          role="status"
        >
          {authError}
        </div>
      ) : null}
      <ChatInput disabled={inputDisabled(state.status)} authReady={authReady} onSubmit={handleSubmit} />
    </section>
  )
}

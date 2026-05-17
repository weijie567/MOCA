import { useState } from 'react'
import { SendHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface ChatInputProps {
  disabled: boolean
  authReady: boolean
  onSubmit: (query: string) => void | Promise<void>
}

export function ChatInput({ disabled, authReady, onSubmit }: ChatInputProps) {
  const [query, setQuery] = useState('')

  function submit() {
    const trimmed = query.trim()
    if (!trimmed || disabled || !authReady) return
    void onSubmit(trimmed)
    setQuery('')
  }

  return (
    <form
      className="border-t border-border bg-card p-4"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <Textarea
        value={query}
        disabled={disabled || !authReady}
        placeholder="输入退款咨询或补偿请求"
        rows={3}
        className="max-h-40"
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            submit()
          }
        }}
      />
      <div className="mt-3 flex justify-end">
        <Button type="submit" disabled={disabled || !authReady || !query.trim()}>
          <SendHorizontal className="mr-2 h-4 w-4" aria-hidden="true" />
          发送问题
        </Button>
      </div>
    </form>
  )
}

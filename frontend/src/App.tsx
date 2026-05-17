import { useEffect, useState } from 'react'
import { AgentTimeline } from '@/components/timeline/AgentTimeline'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { DetailsPanel } from '@/components/details/DetailsPanel'
import { TopBar } from '@/components/layout/TopBar'
import { useAgentRun } from '@/hooks/useAgentRun'
import { useAuth } from '@/hooks/useAuth'
import { getDemoToken, setAuthToken } from '@/lib/api'

function App() {
  const { role, username, switchRole } = useAuth()
  const { state, submitQuery, approveRun, rejectRun } = useAgentRun()
  const [authReady, setAuthReady] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setAuthToken(null)
    setAuthReady(false)
    setAuthError(null)

    void getDemoToken(username)
      .then((result) => {
        if (cancelled) return
        if (result.success) {
          setAuthToken(result.data.access_token)
          setAuthReady(true)
          return
        }
        setAuthReady(false)
        setAuthError(result.error?.message ?? 'Demo token 获取失败，无法执行受保护操作')
      })
      .catch(() => {
        if (!cancelled) {
          setAuthReady(false)
          setAuthError('Demo token 获取失败，无法执行受保护操作')
        }
      })

    return () => {
      cancelled = true
    }
  }, [username])

  return (
    <main className="flex min-h-screen flex-col bg-background text-foreground">
      <TopBar role={role} switchRole={switchRole} />
      <section className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[30fr_35fr_35fr]">
        <ChatPanel
          state={state}
          submitQuery={submitQuery}
          authReady={authReady}
          authError={authError}
        />
        <AgentTimeline steps={state.steps} status={state.status} />
        <DetailsPanel
          runId={state.runId}
          approvalId={state.approvalId}
          status={state.status}
          steps={state.steps}
          approveRun={approveRun}
          rejectRun={rejectRun}
        />
      </section>
    </main>
  )
}

export default App

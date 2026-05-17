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

    void Promise.resolve()
      .then(() => {
        if (cancelled) return null
        setAuthToken(null)
        setAuthReady(false)
        setAuthError(null)
        return getDemoToken(username)
      })
      .then((result) => {
        if (cancelled || !result) return
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
    <main className="flex h-screen overflow-hidden bg-background text-foreground">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <TopBar role={role} switchRole={switchRole} />
        <section className="grid min-h-0 min-w-0 flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[minmax(0,30fr)_minmax(0,35fr)_minmax(0,35fr)]">
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
            role={role}
            status={state.status}
            steps={state.steps}
            approveRun={approveRun}
            rejectRun={rejectRun}
          />
        </section>
      </div>
    </main>
  )
}

export default App

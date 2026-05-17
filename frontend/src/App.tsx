import { AgentTimeline } from '@/components/timeline/AgentTimeline'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { DetailsPanel } from '@/components/details/DetailsPanel'
import { TopBar } from '@/components/layout/TopBar'
import { useAgentRun } from '@/hooks/useAgentRun'
import { useAuth } from '@/hooks/useAuth'

function App() {
  const { role, switchRole } = useAuth()
  const { state, submitQuery, approveRun, rejectRun } = useAgentRun()

  return (
    <main className="flex min-h-screen flex-col bg-background text-foreground">
      <TopBar role={role} switchRole={switchRole} />
      <section className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[30fr_35fr_35fr]">
        <ChatPanel state={state} submitQuery={submitQuery} />
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

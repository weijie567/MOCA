import { useAuth } from '@/hooks/useAuth'

function App() {
  const { role, switchRole } = useAuth()
  return (
    <main className="min-h-screen bg-background text-foreground">
      <header className="flex h-12 items-center justify-between border-b border-border px-4">
        <div className="text-heading font-semibold">MOCA Agent Console</div>
        <label className="flex items-center gap-2 text-label text-muted-foreground">
          Demo Mode
          <select
            className="h-8 rounded-md border border-border bg-card px-2 text-body text-foreground"
            value={role}
            onChange={(event) => switchRole(event.target.value)}
          >
            <option value="support_agent">support_agent</option>
            <option value="manager">manager</option>
            <option value="admin">admin</option>
          </select>
        </label>
      </header>
      <section className="grid min-h-[calc(100vh-3rem)] grid-cols-1 border-border lg:grid-cols-[30fr_35fr_35fr]">
        <div className="border-b border-border p-4 lg:border-b-0 lg:border-r">
          <h1 className="text-display font-semibold">Chat</h1>
          <p className="mt-2 text-body text-muted-foreground">开始一个退款咨询</p>
        </div>
        <div className="border-b border-border p-4 lg:border-b-0 lg:border-r">
          <h2 className="text-heading font-semibold">Agent Timeline</h2>
          <p className="mt-2 text-body text-muted-foreground">等待提交问题后开始执行</p>
        </div>
        <div className="p-4">
          <h2 className="text-heading font-semibold">Details</h2>
          <p className="mt-2 text-body text-muted-foreground">Evidence, Approval, Trace</p>
        </div>
      </section>
    </main>
  )
}

export default App

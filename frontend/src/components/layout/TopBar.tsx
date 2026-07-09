import { ShieldCheck } from 'lucide-react'
import type { DemoRole } from '@/hooks/useAuth'

const ROLE_LABELS: Record<DemoRole, string> = {
  support_agent: '客服专员',
  manager: '审批员',
  admin: '管理员',
}

interface TopBarProps {
  role: DemoRole
  switchRole: (role: string) => void
}

export function TopBar({ role, switchRole }: TopBarProps) {
  return (
    <header className="flex min-h-12 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-4 py-2 lg:h-12 lg:flex-nowrap lg:py-0">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-muted">
          <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
        </div>
        <div className="min-w-0 text-heading font-semibold">MOCA Agent Console</div>
      </div>

      <div className="flex min-w-0 flex-1 items-center justify-end gap-3 sm:flex-none">
        <span className="rounded-md border border-primary/50 bg-primary/10 px-2 py-1 text-label text-primary">
          Demo Mode
        </span>
        <label className="sr-only" htmlFor="demo-role">
          Demo Mode role
        </label>
        <select
          id="demo-role"
          className="h-8 min-w-0 flex-1 rounded-md border border-border bg-background px-2 text-body text-foreground outline-none transition-colors focus:border-primary sm:flex-none"
          value={role}
          onChange={(event) => switchRole(event.target.value)}
        >
          <option value="support_agent">{ROLE_LABELS.support_agent} (Support Agent)</option>
          <option value="manager">{ROLE_LABELS.manager} (Approver)</option>
          <option value="admin">{ROLE_LABELS.admin} (Admin)</option>
        </select>
      </div>
    </header>
  )
}

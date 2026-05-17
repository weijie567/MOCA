import { useState } from 'react'

export type DemoRole = 'support_agent' | 'manager' | 'admin'

const ROLE_USERS: Record<DemoRole, string> = {
  support_agent: 'cs_zhang',
  manager: 'mgr_li',
  admin: 'admin_user',
}

function isDemoRole(value: string): value is DemoRole {
  return value === 'support_agent' || value === 'manager' || value === 'admin'
}

export function useAuth() {
  const [role, setRole] = useState<DemoRole>('support_agent')

  function switchRole(nextRole: string) {
    if (isDemoRole(nextRole)) {
      setRole(nextRole)
    }
  }

  return {
    role,
    username: ROLE_USERS[role],
    switchRole,
  }
}

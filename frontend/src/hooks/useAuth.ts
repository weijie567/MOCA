import { useEffect, useState } from 'react'
import { setAuthToken } from '@/lib/api'

export type DemoRole = 'support_agent' | 'manager' | 'admin'

const ROLE_USERS: Record<DemoRole, string> = {
  support_agent: 'demo-agent',
  manager: 'demo-manager',
  admin: 'demo-admin',
}

function isDemoRole(value: string): value is DemoRole {
  return value === 'support_agent' || value === 'manager' || value === 'admin'
}

export function useAuth() {
  const [role, setRole] = useState<DemoRole>('support_agent')

  useEffect(() => {
    setAuthToken(`demo-token:${ROLE_USERS[role]}`)
  }, [role])

  function switchRole(nextRole: string) {
    if (isDemoRole(nextRole)) {
      setRole(nextRole)
    }
  }

  return {
    role,
    username: ROLE_USERS[role],
    token: `demo-token:${ROLE_USERS[role]}`,
    switchRole,
  }
}

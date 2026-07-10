import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import fixture from '@contracts/fixtures/approval_decision_context_v1.json'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { decideApproval, getApproval, getPendingApprovals, parseApprovalDecisionContext } from '@/lib/api'
import type { ApprovalRecord } from '@/lib/api'
import { ApprovalTab } from './ApprovalTab'

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    decideApproval: vi.fn(),
    getApproval: vi.fn(),
    getPendingApprovals: vi.fn(),
  }
})

const decisionContext = parseApprovalDecisionContext(fixture)!
const record: ApprovalRecord = {
  id: fixture.approval_id,
  run_id: fixture.run_id,
  status: 'pending',
  requested_by: 'requester',
  proposed_action: fixture.proposed_action,
  risk_level: fixture.risk_level,
  risk_rule_ref: fixture.risk_rule_ref,
  risk_reason: fixture.risk_reason,
  decision: null,
  reason: null,
  decided_by: null,
  decided_at: null,
  expires_at: fixture.expires_at,
  created_at: fixture.created_at,
  decision_context: decisionContext,
}

describe('ApprovalTab decision safety', () => {
  afterEach(cleanup)
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getPendingApprovals).mockResolvedValue({ success: true, data: { approvals: [record], total: 1 } })
    vi.mocked(getApproval).mockResolvedValue({ success: true, data: record })
    vi.mocked(decideApproval).mockResolvedValue({ success: true, data: {} })
  })

  it('keeps decisions disabled until latest detail validates and exposes selected semantics', async () => {
    let resolveDetail: ((value: Awaited<ReturnType<typeof getApproval>>) => void) | undefined
    vi.mocked(getApproval).mockReturnValueOnce(new Promise((resolve) => { resolveDetail = resolve }))
    render(<ApprovalTab approvalId={fixture.approval_id} canApprove status="waiting_approval" />)

    await screen.findByText(`run ${fixture.run_id.slice(0, 8)}`)
    expect((screen.getByRole('button', { name: '批准' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByRole('button', { pressed: true })).toBeTruthy()

    resolveDetail?.({ success: true, data: record })
    await waitFor(() => expect((screen.getByRole('button', { name: '批准' }) as HTMLButtonElement).disabled).toBe(false))
  })

  it('uses durable-draft copy and requires a labelled reject reason', async () => {
    render(<ApprovalTab approvalId={fixture.approval_id} canApprove status="waiting_approval" />)
    await waitFor(() => expect((screen.getByRole('button', { name: '批准' }) as HTMLButtonElement).disabled).toBe(false))

    fireEvent.click(screen.getByRole('button', { name: '批准' }))
    expect(screen.getByText(/系统将创建已授权的操作草稿/)).toBeTruthy()
    expect(screen.queryByText(/立即执行/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '取消' }))

    fireEvent.click(screen.getByRole('button', { name: '驳回' }))
    expect(screen.getByLabelText('驳回原因')).toBeTruthy()
    const dialog = screen.getByRole('dialog')
    expect((dialog.querySelector('button.bg-destructive') as HTMLButtonElement).disabled).toBe(true)
  })

  it('echoes the validated frozen context and never double submits', async () => {
    let resolveDecision: ((value: { success: true; data: Record<string, never> }) => void) | undefined
    vi.mocked(decideApproval).mockReturnValueOnce(new Promise((resolve) => { resolveDecision = resolve }))
    render(<ApprovalTab approvalId={fixture.approval_id} canApprove status="waiting_approval" />)
    await waitFor(() => expect((screen.getByRole('button', { name: '批准' }) as HTMLButtonElement).disabled).toBe(false))

    fireEvent.click(screen.getByRole('button', { name: '批准' }))
    const confirm = screen.getAllByRole('button', { name: '批准' }).at(-1)!
    fireEvent.click(confirm)
    fireEvent.click(confirm)
    expect(decideApproval).toHaveBeenCalledTimes(1)
    expect(decideApproval).toHaveBeenCalledWith(decisionContext, { decision_type: 'approve' })
    resolveDecision?.({ success: true, data: {} })
  })
})

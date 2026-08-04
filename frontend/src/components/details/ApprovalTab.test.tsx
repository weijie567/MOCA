import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import fixture from '@contracts/fixtures/approval_decision_context_v1.json'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  decideApproval,
  getApproval,
  getPendingApprovals,
  getRunStatus,
  parseApprovalDecisionContext,
  submitFrozenApprovalSubmission,
} from '@/lib/api'
import type { ApprovalRecord, DecidableApprovalRecord } from '@/lib/api'
import { ApprovalTab } from './ApprovalTab'

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    decideApproval: vi.fn(),
    getApproval: vi.fn(),
    getPendingApprovals: vi.fn(),
    getRunStatus: vi.fn(),
    submitFrozenApprovalSubmission: vi.fn(),
  }
})

const decisionContext = parseApprovalDecisionContext(fixture)!
const record: DecidableApprovalRecord = {
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
const terminalRecord: ApprovalRecord = {
  ...record,
  status: 'approved',
  decision: 'approve',
  decided_at: '2026-07-10T08:00:00Z',
  decision_context: null,
}

describe('ApprovalTab decision safety', () => {
  afterEach(cleanup)
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getPendingApprovals).mockResolvedValue({ success: true, data: { approvals: [record], total: 1 } })
    vi.mocked(getApproval).mockResolvedValue({ success: true, data: record })
    vi.mocked(decideApproval).mockResolvedValue({ success: true, data: terminalRecord })
    vi.mocked(getRunStatus).mockResolvedValue({
      success: true,
      data: { run_id: fixture.run_id, final_status: 'running', final_response: null },
    })
    vi.mocked(submitFrozenApprovalSubmission).mockResolvedValue({ success: true, data: terminalRecord })
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
    let resolveDecision: ((value: { success: true; data: ApprovalRecord }) => void) | undefined
    vi.mocked(decideApproval).mockReturnValueOnce(new Promise((resolve) => { resolveDecision = resolve }))
    render(<ApprovalTab approvalId={fixture.approval_id} canApprove status="waiting_approval" />)
    await waitFor(() => expect((screen.getByRole('button', { name: '批准' }) as HTMLButtonElement).disabled).toBe(false))

    fireEvent.click(screen.getByRole('button', { name: '批准' }))
    const confirm = screen.getAllByRole('button', { name: '批准' }).at(-1)!
    fireEvent.click(confirm)
    fireEvent.click(confirm)
    expect(decideApproval).toHaveBeenCalledTimes(1)
    expect(decideApproval).toHaveBeenCalledWith(decisionContext, { decision_type: 'approve' })
    resolveDecision?.({ success: true, data: terminalRecord })
  })

  it.each([
    ['stale', { kind: 'stale', approval: record } as const, '审批已更新，请查看最新内容后重新决定。'],
    ['ambiguous', { kind: 'ambiguous', approval: record } as const, '提交结果未确认，已查询最新状态。请勿重复提交。'],
    ['unavailable', { kind: 'unavailable', approval: null } as const, '审批不可用或已更新，请返回列表并刷新。'],
  ])('does not announce success when the active callback returns %s', async (_kind, outcome, expectedMessage) => {
    const onApprove = vi.fn().mockResolvedValue(outcome)
    render(
      <ApprovalTab
        approvalId={fixture.approval_id}
        canApprove
        status="waiting_approval"
        onApprove={onApprove}
      />,
    )
    await waitFor(() => expect((screen.getByRole('button', { name: '批准' }) as HTMLButtonElement).disabled).toBe(false))

    fireEvent.click(screen.getByRole('button', { name: '批准' }))
    fireEvent.click(screen.getAllByRole('button', { name: '批准' }).at(-1)!)

    await screen.findByText(expectedMessage)
    expect(screen.queryByText('审批决定已提交，正在同步运行状态。')).toBeNull()
    expect(onApprove).toHaveBeenCalledTimes(1)
    expect(onApprove).toHaveBeenCalledWith(decisionContext)
  })

  it('reconciles committed-but-response-lost direct submission without replay', async () => {
    vi.mocked(getApproval)
      .mockResolvedValueOnce({ success: true, data: record })
      .mockResolvedValueOnce({ success: true, data: terminalRecord })
    vi.mocked(decideApproval).mockResolvedValueOnce({
      success: false,
      data: null,
      error: { code: 'NETWORK_ERROR', message: 'response lost' },
    })
    render(<ApprovalTab approvalId={null} canApprove status="waiting_approval" />)
    await waitFor(() => expect((screen.getByRole('button', { name: '批准' }) as HTMLButtonElement).disabled).toBe(false))

    fireEvent.click(screen.getByRole('button', { name: '批准' }))
    fireEvent.click(screen.getAllByRole('button', { name: '批准' }).at(-1)!)

    await screen.findByText('服务器已确认审批通过，正在同步运行状态。')
    expect(decideApproval).toHaveBeenCalledTimes(1)
    expect(getApproval).toHaveBeenCalledTimes(2)
    expect(screen.queryByText('提交结果未确认，已查询最新状态。请勿重复提交。')).toBeNull()
  })

  it('requires a second confirmation before retrying a committed resume failure', async () => {
    vi.mocked(getApproval)
      .mockResolvedValueOnce({ success: true, data: record })
      .mockResolvedValueOnce({ success: true, data: terminalRecord })
    vi.mocked(decideApproval).mockResolvedValueOnce({
      success: false,
      data: null,
      error: { code: 'APPROVAL_RESUME_FAILED', message: 'decision saved; resume incomplete' },
    })
    render(<ApprovalTab approvalId={null} canApprove status="waiting_approval" />)
    await waitFor(() => expect((screen.getByRole('button', { name: '批准' }) as HTMLButtonElement).disabled).toBe(false))

    fireEvent.click(screen.getByRole('button', { name: '批准' }))
    fireEvent.click(screen.getAllByRole('button', { name: '批准' }).at(-1)!)

    await screen.findAllByText(/审批决定已保存，但运行恢复未完成/)
    expect(screen.queryByText('服务器已确认审批通过，正在同步运行状态。')).toBeNull()
    expect(decideApproval).toHaveBeenCalledTimes(1)
    expect(submitFrozenApprovalSubmission).not.toHaveBeenCalled()
    expect(getApproval).toHaveBeenCalledTimes(2)
    expect(getRunStatus).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: '重试恢复运行' }))
    expect(screen.getByText(/使用已保存的同一审批决定恢复运行/)).toBeTruthy()
    expect(submitFrozenApprovalSubmission).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '重试恢复' }))

    await screen.findByText('运行恢复流程已完成，请查看权威运行终态。')
    expect(submitFrozenApprovalSubmission).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('button', { name: '重试恢复运行' })).toBeNull()
  })
})

import { expect, type Page, test } from '@playwright/test'
import fixture from '../../contracts/fixtures/approval_decision_context_v1.json' with { type: 'json' }

type ApprovalScenario = 'success' | 'stale' | 'ambiguous'

type DecisionContext = typeof fixture

type MockState = {
  capturedBodies: Array<Record<string, unknown>>
  detailReads: number
  decideCalls: number
  cleared: boolean
}

const DRAFT_FAILURE_COPY = '操作草稿创建失败，本次运行未完成。请重试或联系管理员。'
const INPUT_PLACEHOLDER = '输入退款咨询或补偿请求'

function latestContext(overrides: Partial<DecisionContext> = {}): DecisionContext {
  return {
    ...fixture,
    revision: fixture.revision + 1,
    request_version: fixture.request_version + 1,
    ...overrides,
  }
}

function approvalRecord(context: DecisionContext) {
  return {
    id: context.approval_id,
    run_id: context.run_id,
    status: 'pending',
    requested_by: 'phase64-requester',
    proposed_action: context.proposed_action,
    risk_level: context.risk_level,
    risk_rule_ref: context.risk_rule_ref,
    risk_reason: context.risk_reason,
    decision: null,
    reason: null,
    decided_by: null,
    decided_at: null,
    expires_at: context.expires_at,
    created_at: context.created_at,
    decision_context: context,
  }
}

async function mockAuth(page: Page) {
  await page.route('**/api/v1/auth/demo-token', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { access_token: 'phase64-mocked-token' } }),
    })
  })
}

async function mockApprovalApi(
  page: Page,
  scenario: ApprovalScenario,
  context: DecisionContext = latestContext(),
): Promise<MockState> {
  const state: MockState = {
    capturedBodies: [],
    detailReads: 0,
    decideCalls: 0,
    cleared: false,
  }
  const listContext = { ...context, revision: context.revision - 1, request_version: context.request_version - 1 }

  await page.route(/\/api\/v1\/approvals(?:\?.*)?$/, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.fallback()
      return
    }
    const approvals = state.cleared ? [] : [approvalRecord(listContext)]
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { approvals, total: approvals.length } }),
    })
  })

  await page.route(new RegExp(`/api/v1/approvals/${context.approval_id}$`), async (route) => {
    state.detailReads += 1
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: approvalRecord(context) }),
    })
  })

  await page.route(new RegExp(`/api/v1/approvals/${context.approval_id}/decide$`), async (route) => {
    state.decideCalls += 1
    state.capturedBodies.push(route.request().postDataJSON() as Record<string, unknown>)
    if (scenario === 'ambiguous') {
      await route.abort('connectionfailed')
      return
    }
    if (scenario === 'stale') {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: { code: 'CONFLICT', message: 'stale decision context' },
        }),
      })
      return
    }
    state.cleared = true
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { status: 'approved' } }),
    })
  })

  return state
}

async function openApprovalTab(page: Page) {
  await page.goto('/')
  await page.getByLabel('Demo Mode role').selectOption('admin')
  await expect(page.getByPlaceholder(INPUT_PLACEHOLDER)).toBeEnabled()
  await page.getByRole('button', { name: 'Approval', exact: true }).click()
  await expect(page.getByText(`run ${fixture.run_id.slice(0, 8)}`)).toBeVisible()
  await expect(page.locator('button[aria-pressed="true"]')).toBeVisible()
  await expect(page.getByRole('button', { name: '批准', exact: true }).first()).toBeEnabled()
}

test.describe('Phase 64.1 mocked approval safety', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuth(page)
  })

  test('approves only the latest detail snapshot and keeps durable-draft copy', async ({ page }) => {
    const context = latestContext()
    const state = await mockApprovalApi(page, 'success', context)
    await openApprovalTab(page)

    await page.getByRole('button', { name: '批准', exact: true }).first().click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toHaveAttribute('aria-modal', 'true')
    await expect(dialog.getByText(/系统将创建已授权的操作草稿/)).toBeVisible()
    await expect(dialog.getByText(/不会直接执行生产外部操作/)).toBeVisible()
    await expect(dialog.getByText(/立即执行/)).toHaveCount(0)
    await dialog.getByRole('button', { name: '批准', exact: true }).click()

    await expect(page.getByText('审批决定已提交，正在同步运行状态。')).toBeVisible()
    expect(state.decideCalls).toBe(1)
    expect(state.detailReads).toBeGreaterThanOrEqual(1)
    expect(state.capturedBodies).toEqual([
      {
        decision_type: 'approve',
        expected_request_version: context.request_version,
        expected_level_version: context.level_version,
        expected_assignment_version: context.assignment_version,
        expected_revision: context.revision,
        action_payload_hash: context.action_payload_hash,
        safety_snapshot_hash: context.safety_snapshot_hash,
      },
    ])
    expect(state.capturedBodies[0]).not.toHaveProperty('decision')
    await expect(page.getByText(/操作已成功执行/)).toHaveCount(0)
  })

  test('rejects with a labelled non-empty reason from the same latest context', async ({ page }) => {
    const context = latestContext()
    const state = await mockApprovalApi(page, 'success', context)
    await openApprovalTab(page)

    await page.getByRole('button', { name: '驳回', exact: true }).first().click()
    const dialog = page.getByRole('dialog')
    const reason = dialog.getByLabel('驳回原因')
    await expect(reason).toHaveAttribute('aria-describedby', 'reject-reason-help')
    await expect(dialog.getByRole('button', { name: '驳回', exact: true })).toBeDisabled()
    await reason.fill('超出当前补偿政策')
    await dialog.getByRole('button', { name: '驳回', exact: true }).click()

    await expect(page.getByText('审批决定已提交，正在同步运行状态。')).toBeVisible()
    expect(state.decideCalls).toBe(1)
    expect(state.capturedBodies[0]).toMatchObject({
      decision_type: 'reject',
      reason: '超出当前补偿政策',
      expected_revision: context.revision,
      action_payload_hash: context.action_payload_hash,
      safety_snapshot_hash: context.safety_snapshot_hash,
    })
  })

  test('stale detail fails closed, refreshes once, and never replays the POST', async ({ page }) => {
    const state = await mockApprovalApi(page, 'stale')
    await openApprovalTab(page)

    await page.getByRole('button', { name: '批准', exact: true }).first().click()
    await page.getByRole('dialog').getByRole('button', { name: '批准', exact: true }).click()

    await expect(page.getByText('审批已更新，请查看最新内容后重新决定。')).toBeVisible()
    expect(state.decideCalls).toBe(1)
    expect(state.detailReads).toBeGreaterThanOrEqual(2)
    await expect(page.getByRole('button', { name: '批准', exact: true }).first()).toBeDisabled()
  })

  test('ambiguous submit queries latest state without automatic replay', async ({ page }) => {
    const state = await mockApprovalApi(page, 'ambiguous')
    await openApprovalTab(page)

    await page.getByRole('button', { name: '批准', exact: true }).first().click()
    await page.getByRole('dialog').getByRole('button', { name: '批准', exact: true }).click()

    await expect(page.getByText('提交结果未确认，正在查询最新状态。请勿重复提交。')).toBeVisible()
    expect(state.decideCalls).toBe(1)
    expect(state.detailReads).toBeGreaterThanOrEqual(2)
  })

  test('draft failure becomes an error terminal, never completed success', async ({ page }) => {
    const runId = 'mock-run-phase64-1'

    await page.route(/\/api\/v1\/agent-runs$/, async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { run_id: runId, status: 'pending' } }),
      })
    })
    await page.route(new RegExp(`/api/v1/agent-runs/${runId}/events$`), async (route) => {
      const event = {
        event_type: 'error',
        run_id: runId,
        step_index: 4,
        node_name: 'terminal_error',
        status: 'failed',
        message: DRAFT_FAILURE_COPY,
        timestamp: new Date().toISOString(),
        payload: {
          error_code: 'ACTION_DRAFT_TERMINAL_FAILED',
          error_message: DRAFT_FAILURE_COPY,
        },
      }
      await route.fulfill({
        contentType: 'text/event-stream',
        headers: { 'Cache-Control': 'no-cache' },
        body: `data: ${JSON.stringify(event)}\n\n`,
      })
    })

    await page.goto('/')
    await page.getByLabel('Demo Mode role').selectOption('admin')
    const input = page.getByPlaceholder(INPUT_PLACEHOLDER)
    await expect(input).toBeEnabled()
    await input.fill('请创建需要审批的补偿草稿')
    await page.getByRole('button', { name: '发送问题' }).click()

    await expect(page.getByText(DRAFT_FAILURE_COPY).first()).toBeVisible({ timeout: 8_000 })
    await expect(page.getByText('terminal_error · status: failed')).toBeVisible()
    await expect(page.getByText('completed', { exact: true })).toHaveCount(0)
    await expect(page.getByText(/操作已成功执行/)).toHaveCount(0)
  })
})

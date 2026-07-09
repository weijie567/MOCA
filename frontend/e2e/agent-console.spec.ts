import { expect, type Page, test } from '@playwright/test'

type MockScenario = {
  finalResponse: string
  events: Array<{
    event_type: 'run_started' | 'step_started' | 'step_completed' | 'final_response'
    step_index: number
    node_name: string | null
    status: string
    message: string
    payload?: Record<string, unknown>
  }>
}

const INPUT_PLACEHOLDER = '输入退款咨询或补偿请求'
const SEND_BUTTON = '发送问题'
const API_URL =
  process.env.MOCA_E2E_API_URL ??
  (process.env.MOCA_E2E_LIVE ? 'http://127.0.0.1:8011' : 'http://127.0.0.1:8000')

const MOCK_SCENARIOS: Record<string, MockScenario> = {
  你好: {
    finalResponse: '你好，我是 MOCA，可以帮你查询具体订单、退款单或工单。',
    events: [
      runStarted(),
      finalResponse('直接回复完成', {
        final_response: '你好，我是 MOCA，可以帮你查询具体订单、退款单或工单。',
        response_kind: 'small_talk',
      }),
    ],
  },
  当前有多少订单: {
    finalResponse: '要统计该指标，请选择时间范围：今天、本周、本月、本季度、今年，或指定起止时间。',
    events: [
      runStarted(),
      finalResponse('需要补充信息', {
        final_response: '要统计该指标，请选择时间范围：今天、本周、本月、本季度、今年，或指定起止时间。',
        response_kind: 'clarification',
        safe_reason: 'missing_time_range',
      }),
    ],
  },
  今天有多少退款单: {
    finalResponse: '3（退款单数）。\n范围：当前权限范围；时间：today；筛选：无；新鲜度：当前可用业务数据。',
    events: [
      runStarted(),
      stepCompleted('investigate', '正在调查订单和规则', {
        response_kind: 'metric_answer',
        metric_id: 'refund_case_count',
        metric_label: '退款单数',
        scope_label: '当前权限范围',
        tool_name: 'query_business_metric',
        tool_label: '查询业务指标',
      }),
      finalResponse('已完成', {
        final_response: '3（退款单数）。\n范围：当前权限范围；时间：today；筛选：无；新鲜度：当前可用业务数据。',
        response_kind: 'metric_answer',
        metric: {
          metric_id: 'refund_case_count',
          metric_label: '退款单数',
          scope_label: '当前权限范围',
          safe_reason: 'ok',
        },
      }),
    ],
  },
  帮我预测下个月GMV: {
    finalResponse: '当前不支持该统计口径。你可以查询订单数、退款单数、待处理工单数、补偿券记录数或商家退款率。',
    events: [
      runStarted(),
      finalResponse('当前能力不支持', {
        final_response: '当前不支持该统计口径。你可以查询订单数、退款单数、待处理工单数、补偿券记录数或商家退款率。',
        response_kind: 'unsupported',
        safe_reason: 'unsupported_metric',
      }),
    ],
  },
  '查询商户 MERCHANT-SECRET 本月退款率': {
    finalResponse: '当前权限范围内无法提供该商户指标。',
    events: [
      runStarted(),
      finalResponse('已完成', {
        final_response: '当前权限范围内无法提供该商户指标。',
        response_kind: 'metric_answer',
        metric: {
          metric_id: 'merchant_refund_rate',
          metric_label: '商户退款率',
          scope_label: '当前权限范围',
          safe_reason: 'scope_denied_no_existence_leak',
        },
      }),
    ],
  },
  本周多少订单: {
    finalResponse: '本周订单 128 单。范围：当前权限范围；时间：本周；筛选：无；新鲜度：当前可用业务数据。',
    events: [
      runStarted(),
      finalResponse('业务汇总查询完成', {
        final_response: '本周订单 128 单。范围：当前权限范围；时间：本周；筛选：无；新鲜度：当前可用业务数据。',
        response_kind: 'business_query_answer',
        business_query: {
          operation: 'aggregate',
          resource_label: '订单',
          result_label: '本周订单 128 单',
          scope_label: '当前权限范围',
          time_label: '本周',
          filters_label: '无',
          freshness_label: '当前可用业务数据',
        },
        raw_args: { tenant_id: 'tenant-secret' },
      }),
    ],
  },
  订单号是多少: {
    finalResponse: '当前权限范围内找到 2 个订单：ORD-SAFE-1、ORD-SAFE-2。可继续查看更多。',
    events: [
      runStarted(),
      finalResponse('业务列表查询完成', {
        final_response: '当前权限范围内找到 2 个订单：ORD-SAFE-1、ORD-SAFE-2。可继续查看更多。',
        response_kind: 'business_query_answer',
        business_query: {
          operation: 'list',
          resource_label: '订单',
          result_label: '订单列表',
          scope_label: '当前权限范围',
          row_count: 2,
          limit: 20,
          cursor_label: '查看更多',
          allowed_drilldowns: ['detail'],
          rows: [
            { 订单号: 'ORD-SAFE-1', 状态: '已支付', raw_payload: 'SHOULD_NOT_RENDER' },
            { 订单号: 'ORD-SAFE-2', 状态: '已完成', tenant_id: 'tenant-secret' },
          ],
        },
        raw_cursor: 'cursor-secret',
      }),
    ],
  },
  查看退款单详情: {
    finalResponse: '退款单详情已返回：RF-SAFE-1，状态待处理。',
    events: [
      runStarted(),
      finalResponse('业务详情查询完成', {
        final_response: '退款单详情已返回：RF-SAFE-1，状态待处理。',
        response_kind: 'business_query_answer',
        business_query: {
          operation: 'detail',
          resource_label: '退款单',
          result_label: '退款单详情',
          fields_label: '退款单号、状态、金额',
          rows: [{ 退款单号: 'RF-SAFE-1', 状态: '待处理', merchant_scope: 'merchant-secret' }],
        },
      }),
    ],
  },
  按状态分组订单: {
    finalResponse: '按订单状态分组：已支付 8，已完成 12。',
    events: [
      runStarted(),
      finalResponse('业务分组查询完成', {
        final_response: '按订单状态分组：已支付 8，已完成 12。',
        response_kind: 'business_query_answer',
        business_query: {
          operation: 'breakdown',
          resource_label: '订单',
          result_label: '订单状态分组',
          group_by_label: '订单状态',
          rows: [
            { 分组: '已支付', 数量: 8 },
            { 分组: '已完成', 数量: 12 },
          ],
        },
      }),
    ],
  },
  对比本周和上周订单: {
    finalResponse: '本周 vs 上周订单量对比：本周 128，上周 118，变化 +8%。',
    events: [
      runStarted(),
      finalResponse('业务对比查询完成', {
        final_response: '本周 vs 上周订单量对比：本周 128，上周 118，变化 +8%。',
        response_kind: 'business_query_answer',
        business_query: {
          operation: 'compare',
          resource_label: '订单',
          result_label: '订单量对比',
          compare_label: '本周 vs 上周',
          rows: [
            { 对比项: '本周', 数量: 128, 变化: '+8%' },
            { 对比项: '上周', 数量: 118 },
          ],
        },
      }),
    ],
  },
  查询无权限订单: {
    finalResponse: '当前权限范围内无法提供该业务数据。',
    events: [
      runStarted(),
      finalResponse('业务列表查询完成', {
        final_response: '当前权限范围内无法提供该业务数据。',
        response_kind: 'business_query_answer',
        business_query: {
          operation: 'list',
          resource_label: '订单',
          safe_reason: 'scope_denied_no_existence_leak',
          rows: [],
          row_count: 0,
          raw_args: { merchant_id: 'MERCHANT-SECRET' },
        },
      }),
    ],
  },
  查询空订单列表: {
    finalResponse: '当前权限范围和筛选条件下没有可显示的结果。',
    events: [
      runStarted(),
      finalResponse('业务列表查询完成', {
        final_response: '当前权限范围和筛选条件下没有可显示的结果。',
        response_kind: 'business_query_answer',
        business_query: {
          operation: 'list',
          resource_label: '订单',
          safe_reason: 'empty_result',
          rows: [],
          row_count: 0,
        },
      }),
    ],
  },
}

test.describe('Agent Console mocked Phase 61 flows', () => {
  test.beforeEach(async ({ page }) => {
    await mockAgentApi(page)
  })

  test('renders safe timeline labels for known Phase 61 prompts', async ({ page }, testInfo) => {
    await page.goto('/')
    await expect(page.getByPlaceholder(INPUT_PLACEHOLDER)).toBeEnabled()

    await submitAndExpect(page, '你好', {
      responseText: '你好，我是 MOCA',
      timelineText: '直接回复',
      subtitleText: 'response: direct',
    })
    await submitAndExpect(page, '当前有多少订单', {
      responseText: '请选择时间范围',
      timelineText: '需要补充信息',
      subtitleText: '原因: 缺少时间范围',
    })
    await submitAndExpect(page, '今天有多少退款单', {
      responseText: '3（退款单数）',
      timelineText: '业务指标查询完成',
      subtitleText: 'metric: 退款单数 · scope: 当前权限范围',
    })
    await submitAndExpect(page, '帮我预测下个月GMV', {
      responseText: '当前不支持该统计口径',
      timelineText: '当前能力不支持',
      subtitleText: '原因: 不支持的统计口径',
    })
    await submitAndExpect(page, '查询商户 MERCHANT-SECRET 本月退款率', {
      responseText: '当前权限范围内无法提供该商户指标',
      timelineText: '业务指标查询完成',
      subtitleText: 'metric: 商户退款率 · scope: 当前权限范围',
    })

    await expect(page.getByText('MERCHANT-SECRET')).toHaveCount(1)
    await expect(page.getByText('routing_hints')).toHaveCount(0)
    await expect(page.getByText('raw_args')).toHaveCount(0)
    await expectTimelineRowsDoNotOverlap(page)
    await page.screenshot({ path: testInfo.outputPath('agent-console-mocked.png'), fullPage: true })
  })
})

test.describe('Agent Console mocked Phase 62 business query flows', () => {
  test.beforeEach(async ({ page }) => {
    await mockAgentApi(page)
  })

  test('renders typed business query Result tab and aggregate-to-list drilldown sequence safely', async ({ page }, testInfo) => {
    await page.goto('/')
    await expect(page.getByPlaceholder(INPUT_PLACEHOLDER)).toBeEnabled()

    await submitAndExpect(page, '本周多少订单', {
      responseText: '本周订单 128 单',
      timelineText: '业务汇总查询完成',
      subtitleText: 'aggregate: 本周订单 128 单 · scope: 当前权限范围',
    })
    await expect(page.getByRole('button', { name: 'Result' })).toBeVisible()
    await expect(page.getByText('本周订单 128 单').last()).toBeVisible()

    await submitAndExpect(page, '订单号是多少', {
      responseText: 'ORD-SAFE-1',
      timelineText: '业务列表查询完成',
      subtitleText: 'list: 订单 · rows: 2/20',
    })
    await expect(page.getByText('ORD-SAFE-2')).toBeVisible()
    await expect(page.getByRole('button', { name: '查看更多' })).toBeVisible()
    await expect(page.getByRole('button', { name: '查看详情' }).first()).toBeVisible()

    for (const text of ['raw_args', 'raw_payload', 'raw_cursor', 'tenant-secret', 'cursor-secret', 'SHOULD_NOT_RENDER']) {
      await expect(page.getByText(text)).toHaveCount(0)
    }
    await expectTimelineRowsDoNotOverlap(page)
    await expectResultPanelDoesNotOverflow(page)
    await page.screenshot({ path: testInfo.outputPath('agent-console-business-query-drilldown.png'), fullPage: true })
  })

  test('renders detail, breakdown, compare, denied, and empty business query states safely', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByPlaceholder(INPUT_PLACEHOLDER)).toBeEnabled()

    await submitAndExpect(page, '查看退款单详情', {
      responseText: 'RF-SAFE-1',
      timelineText: '业务详情查询完成',
      subtitleText: 'detail: 退款单 · fields: 退款单号、状态、金额',
    })
    await expect(page.getByText('待处理').first()).toBeVisible()

    await submitAndExpect(page, '按状态分组订单', {
      responseText: '已支付 8',
      timelineText: '业务分组查询完成',
      subtitleText: 'breakdown: 订单 · by: 订单状态',
    })
    await expect(page.getByText('已完成').first()).toBeVisible()

    await submitAndExpect(page, '对比本周和上周订单', {
      responseText: '变化 +8%',
      timelineText: '业务对比查询完成',
      subtitleText: 'compare: 订单量对比 · 本周 vs 上周',
    })
    await expect(page.getByText('+8%').first()).toBeVisible()

    await submitAndExpect(page, '查询无权限订单', {
      responseText: '当前权限范围内无法提供该业务数据',
      timelineText: '业务列表查询完成',
      subtitleText: 'list: 订单 · rows: 0',
    })
    await expect(page.getByText('当前权限范围内无法提供该业务数据。').first()).toBeVisible()

    await submitAndExpect(page, '查询空订单列表', {
      responseText: '当前权限范围和筛选条件下没有可显示的结果',
      timelineText: '业务列表查询完成',
      subtitleText: 'list: 订单 · rows: 0',
    })
    await expect(page.getByText('当前权限范围和筛选条件下没有可显示的结果。').first()).toBeVisible()

    for (const text of ['merchant_scope', 'MERCHANT-SECRET', 'raw_args']) {
      await expect(page.getByText(text)).toHaveCount(0)
    }
    await expectTimelineRowsDoNotOverlap(page)
    await expectResultPanelDoesNotOverflow(page)
  })
})

test.describe('Agent Console live Phase 61 flows @live', () => {
  test('uses real agent-runs SSE for direct-response smoke', async ({ page, request }, testInfo) => {
    test.skip(!process.env.MOCA_E2E_LIVE, 'Run via npm run e2e:live')

    const health = await request.get(`${API_URL}/health`)
    expect(health.ok(), `Backend health check failed: ${health.status()} ${await health.text()}`).toBeTruthy()

    let sawCreateRun = false
    let sawRunEvents = false
    page.on('response', (response) => {
      const url = response.url()
      if (url.includes('/api/v1/agent-runs') && response.request().method() === 'POST') {
        sawCreateRun = true
      }
      if (url.includes('/api/v1/agent-runs/') && url.endsWith('/events')) {
        sawRunEvents = true
      }
    })

    await page.goto('/')
    await expect(page.getByPlaceholder(INPUT_PLACEHOLDER)).toBeEnabled()

    await submitAndExpect(page, '你好', {
      responseText: '你好',
      timelineText: '直接回复',
      subtitleText: 'response: direct',
    })

    expect(sawCreateRun).toBeTruthy()
    expect(sawRunEvents).toBeTruthy()
    await expectTimelineRowsDoNotOverlap(page)
    await page.screenshot({ path: testInfo.outputPath('agent-console-live-smoke.png'), fullPage: true })
  })

  test('uses real agent-runs SSE for full demo prompt matrix @full-live', async ({ page, request }, testInfo) => {
    test.skip(!process.env.MOCA_E2E_FULL_LIVE, 'Requires live LLM provider: set MOCA_E2E_FULL_LIVE=1')

    const health = await request.get(`${API_URL}/health`)
    expect(health.ok(), `Backend health check failed: ${health.status()} ${await health.text()}`).toBeTruthy()

    let sawCreateRun = false
    let sawRunEvents = false
    page.on('response', (response) => {
      const url = response.url()
      if (url.includes('/api/v1/agent-runs') && response.request().method() === 'POST') {
        sawCreateRun = true
      }
      if (url.includes('/api/v1/agent-runs/') && url.endsWith('/events')) {
        sawRunEvents = true
      }
    })

    await page.goto('/')
    await expect(page.getByPlaceholder(INPUT_PLACEHOLDER)).toBeEnabled()

    await submitAndExpect(page, '你好', {
      responseText: '你好',
      timelineText: '直接回复',
      subtitleText: 'response: direct',
    })
    await submitAndExpect(page, '当前有多少订单', {
      responseText: '时间范围',
      timelineText: '需要补充信息',
      subtitleText: '原因: 缺少时间范围',
    })
    await submitAndExpect(page, '今天有多少退款单', {
      responseText: '范围：当前权限范围',
      timelineText: '业务指标查询完成',
      subtitleText: 'scope: 当前权限范围',
    })
    await submitAndExpect(page, '帮我预测下个月GMV', {
      responseText: '当前',
      timelineText: '当前能力不支持',
      subtitleText: '原因:',
    })
    await submitAndExpect(page, '查询商户 MERCHANT-SECRET 本月退款率', {
      responseText: '当前权限范围内无法提供该商户指标',
      timelineText: '业务指标查询完成',
      subtitleText: 'scope: 当前权限范围',
    })

    expect(sawCreateRun).toBeTruthy()
    expect(sawRunEvents).toBeTruthy()
    await expectTimelineRowsDoNotOverlap(page)
    await page.screenshot({ path: testInfo.outputPath('agent-console-live.png'), fullPage: true })
  })
})

async function mockAgentApi(page: Page) {
  let runCounter = 0
  const runQueries = new Map<string, string>()

  await page.route('**/api/v1/auth/demo-token', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { access_token: 'mock-demo-token' },
      }),
    })
  })

  await page.route('**/api/v1/agent-runs', async (route) => {
    const request = route.request()
    if (request.method() !== 'POST') {
      await route.fallback()
      return
    }
    const body = request.postDataJSON() as { query?: string }
    runCounter += 1
    const runId = `mock-run-${runCounter}`
    runQueries.set(runId, body.query ?? '')
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { run_id: runId, status: 'pending' },
      }),
    })
  })

  await page.route(/\/api\/v1\/agent-runs\/([^/]+)\/events$/, async (route) => {
    const match = route.request().url().match(/\/api\/v1\/agent-runs\/([^/]+)\/events$/)
    const runId = match?.[1] ?? ''
    const query = runQueries.get(runId) ?? ''
    const scenario = MOCK_SCENARIOS[query] ?? MOCK_SCENARIOS['帮我预测下个月GMV']
    const now = new Date().toISOString()
    const stream = scenario.events
      .map((event) =>
        `data: ${JSON.stringify({
          run_id: runId,
          timestamp: now,
          ...event,
          payload: event.payload ?? {},
        })}\n\n`,
      )
      .join('')
    await route.fulfill({
      contentType: 'text/event-stream',
      headers: {
        'Cache-Control': 'no-cache',
      },
      body: stream,
    })
  })

  await page.route(/\/api\/v1\/agent-runs\/[^/]+(\/evidence|\/trace)?$/, async (route) => {
    const url = route.request().url()
    const data = url.endsWith('/evidence')
      ? { evidence: [] }
      : url.endsWith('/trace')
        ? { run_id: 'mock-run', steps: [], timeline: [] }
        : { run_id: 'mock-run', final_status: 'completed', final_response: null }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data,
      }),
    })
  })
}

async function submitAndExpect(
  page: Page,
  query: string,
  expected: { responseText: string; timelineText: string; subtitleText: string },
) {
  await page.getByPlaceholder(INPUT_PLACEHOLDER).fill(query)
  await page.getByRole('button', { name: SEND_BUTTON }).click()
  await expect(page.getByText(expected.responseText, { exact: false }).first()).toBeVisible()
  await expect(page.getByText(expected.timelineText, { exact: false }).first()).toBeVisible()
  await expect(page.getByText(expected.subtitleText, { exact: false }).first()).toBeVisible()
}

async function expectTimelineRowsDoNotOverlap(page: Page) {
  const rows = page.locator('ol > li')
  const count = await rows.count()
  expect(count).toBeGreaterThan(0)

  let previousBottom = 0
  for (let index = 0; index < count; index += 1) {
    const box = await rows.nth(index).boundingBox()
    expect(box, `timeline row ${index} should have a layout box`).not.toBeNull()
    if (!box) continue
    expect(box.width).toBeGreaterThan(160)
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.y).toBeGreaterThanOrEqual(previousBottom - 1)
    previousBottom = box.y + box.height
  }
}

async function expectResultPanelDoesNotOverflow(page: Page) {
  const resultButton = page.getByRole('button', { name: 'Result' })
  await expect(resultButton).toBeVisible()
  const detailsPanel = page.getByRole('heading', { name: 'Details' }).locator('..').locator('..')
  const panelBox = await detailsPanel.boundingBox()
  expect(panelBox, 'Details panel should have a layout box').not.toBeNull()
  if (!panelBox) return
  expect(panelBox.width).toBeGreaterThan(240)
  expect(panelBox.x).toBeGreaterThanOrEqual(0)
}

function runStarted() {
  return {
    event_type: 'run_started' as const,
    step_index: 0,
    node_name: null,
    status: 'running',
    message: '正在接收请求',
    payload: {},
  }
}

function stepCompleted(nodeName: string, message: string, payload: Record<string, unknown>) {
  return {
    event_type: 'step_completed' as const,
    step_index: 1,
    node_name: nodeName,
    status: 'completed',
    message,
    payload,
  }
}

function finalResponse(message: string, payload: Record<string, unknown>) {
  return {
    event_type: 'final_response' as const,
    step_index: 2,
    node_name: 'final_response',
    status: 'completed',
    message,
    payload,
  }
}

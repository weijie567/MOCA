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

test.describe('Agent Console live Phase 61 flows @live', () => {
  test('uses real agent-runs SSE for demo prompts', async ({ page, request }, testInfo) => {
    test.skip(!process.env.MOCA_E2E_LIVE, 'Run via npm run e2e:live')

    const health = await request.get('/api/v1/health')
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

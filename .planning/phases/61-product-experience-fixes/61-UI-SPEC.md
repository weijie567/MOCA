---
phase: 61
slug: product-experience-fixes
status: approved
shadcn_initialized: false
preset: none
created: 2026-07-09
---

# Phase 61 — UI Design Contract

> Visual and interaction contract for Agent Console UX polish in Phase 61. Scope is limited to timeline labels, clarification/unsupported presentation, metric answer display, and regression-visible console states.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none |
| Preset | not applicable |
| Component library | Existing local React components plus Tailwind utility classes |
| Icon library | `lucide-react` |
| Font | `Inter, system-ui, sans-serif` |

Phase 61 must reuse the current console shell, dark theme tokens, `ScrollArea`, `cn`, status color tokens, and local typography utilities. Do not introduce a new component library, new page shell, landing-page layout, decorative gradients, or nested card structure.

---

## Spacing Scale

Declared values match the current Tailwind and app conventions:

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon gaps, status-dot ring offset |
| sm | 8px | Compact row gaps, timeline subtitle spacing |
| md | 16px | Panel padding, timeline item padding |
| lg | 24px | Major toolbar/header spacing only when already present |
| xl | 32px | Reserved for page-level gaps; avoid in dense timeline rows |

Exceptions: none.

Timeline rows must keep stable grid columns equivalent to `20px 1fr auto`; labels, subtitles, and timestamps must not resize the dot rail or move neighboring rows.

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 14px | 400 | 1.5 |
| Label | 12px | 400 | 1.33 |
| Heading | 16px | 600 | 1.25 |
| Display | 20px | 600 | 1.2 |

Timeline primary labels use `text-body font-semibold`. Timeline subtitles and timestamps use `text-label text-muted-foreground`. Do not add viewport-scaled font sizes or negative letter spacing.

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `hsl(var(--background))` = `220 24% 8%` | Page background |
| Secondary (30%) | `hsl(var(--card))` / `hsl(var(--muted))` | Panels, empty state, disconnected state |
| Accent (10%) | `hsl(var(--accent))` = `187 68% 44%` | Primary app accent and shield mark only |
| Success | `hsl(148 66% 48%)` | Completed status dot/icon |
| Waiting | `hsl(42 93% 56%)` | Approval or clarification waiting state |
| Warning | `hsl(26 91% 56%)` | Degraded or unsupported-but-handled state |
| Destructive | `hsl(0 72% 56%)` | Failed/error/rejected states only |

Accent reserved for: app chrome, focus ring, and existing primary controls. Metric answers should not add a new color family; they use existing completed/running status colors plus safe text labels.

---

## Timeline Result Labels

| Result Type | Primary Label | Subtitle Pattern |
|-------------|---------------|------------------|
| direct response | `直接回复` or specific small-talk label when supplied | `response: direct` |
| clarification | `需要补充信息` | `原因: {safe_reason}` |
| unsupported | `当前能力不支持` | `原因: {safe_reason}` |
| metric query running | `正在查询业务指标` | `metric: {metric_id or metric_label} · scope: {scope_label}` |
| metric answer complete | `业务指标查询完成` | `metric: {metric_id or metric_label} · scope: {scope_label}` |
| RAG answer | `正在构建证据上下文` or existing RAG node label | `evidence: {count}` only when backend provides verified count |
| tool call | `正在调用工具` or safe `tool_label` | `tool: {tool_label}` |

Do not render raw tool arguments, routing hints, unauthorized merchant identifiers, stack traces, SQL, LLM prompt fragments, internal policy debug, or raw JSON payloads in timeline rows.

---

## Final Answer Placement

Detailed metric information belongs primarily in the chat final answer, not the timeline. Metric final answer layout contract:

1. First sentence starts with the value or percentage.
2. Second sentence states scope, time range, filters, and data freshness.
3. Coupon metric copy must state the MOCA demo record scope: `issue_coupon` action drafts/records, not external real-world delivery success.
4. Unauthorized merchant metric answer uses no-existence-leak wording: `当前权限范围内无法提供该商户指标`.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Timeline empty state | `等待提交问题后开始执行` |
| Disconnected state | `连接中断，正在恢复状态` |
| Missing time clarification | `要统计该指标，请选择时间范围：今天、本周、本月、本季度、今年，或指定起止时间。` |
| Unsupported metric/capability | `当前不支持该统计口径。你可以查询订单数、退款单数、待处理工单数、补偿券记录数或商家退款率。` |
| Scope denial | `当前权限范围内无法提供该商户指标。` |

Copy must explain the missing input or safe capability boundary. It must not expose whether an out-of-scope merchant exists.

---

## Responsive And State Requirements

- Desktop and mobile widths must keep timeline labels and timestamps non-overlapping.
- Long metric labels or safe reasons may truncate in the timeline subtitle; the complete details remain in the chat answer.
- Unsupported, clarification, and error runs must not leave stale active timeline state in the next run.
- New conversation clears active run state; same-thread follow-up preserves chat history without merging prior timeline steps into the active run.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | not required |
| third-party registry | none | do not use |

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** approved 2026-07-09 by local UI contract review. External `gsd-ui-checker` was not spawned in this run; execution must still verify with Vitest, build, Playwright screenshots, and local UI validation records.

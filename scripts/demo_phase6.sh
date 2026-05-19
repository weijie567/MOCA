#!/usr/bin/env bash
# MOCA Demo Script - 7 scenarios demonstrating the agent workflow system
# Prerequisites: docker compose up, make migrate, make seed
# Usage: bash scripts/demo_phase6.sh

set -euo pipefail

BASE_URL="${MOCA_BASE_URL:-http://localhost:8000}"
AGENT_TOKEN=""
MANAGER_TOKEN=""
APPROVAL_ID=""
LAST_RUN_ID=""
LAST_CHAT_RESPONSE=""

require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    echo "FAIL: jq is required for formatted demo output"
    echo "  Fix: install jq, then rerun this script"
    exit 1
  fi
}

print_header() {
  local scenario="$1"
  local title="$2"

  echo ""
  echo "========================================"
  echo " Demo ${scenario}: ${title}"
  echo "========================================"
  echo ""
}

print_chat_summary() {
  local response="$1"

  echo "$response" | jq .
  echo ""
  echo "Key fields:"
  echo "  success: $(echo "$response" | jq -r '.success')"
  echo "  run_id: $(echo "$response" | jq -r '.data.trace_summary.run_id // .data.run_id // "n/a"')"
  echo "  intent: $(echo "$response" | jq -r '.data.trace_summary.intent // "n/a"')"
  echo "  risk_level: $(echo "$response" | jq -r '.data.trace_summary.risk_level // .data.risk_level // "n/a"')"
  echo "  evidence_count: $(echo "$response" | jq -r '.data.trace_summary.evidence_count // "n/a"')"
  echo "  final_status: $(echo "$response" | jq -r '.data.trace_summary.final_status // .data.status // "n/a"')"
}

post_chat() {
  local scenario="$1"
  local title="$2"
  local query="$3"
  local thread_id="$4"
  local response

  if ! response=$(curl -s -X POST "$BASE_URL/api/v1/agent/chat" \
    -H "Authorization: Bearer $AGENT_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"${query}\",\"thread_id\":\"${thread_id}\"}"); then
    echo "FAIL at demo step ${scenario}: ${title}"
    echo "  curl returned non-zero exit code"
    echo "  Check: docker compose logs api | tail -20"
    exit 1
  fi

  echo "Response:"
  print_chat_summary "$response"
  LAST_CHAT_RESPONSE="$response"
  LAST_RUN_ID=$(echo "$response" | jq -r '.data.trace_summary.run_id // .data.run_id // empty')
}

preflight() {
  echo "Running preflight checks..."

  if ! curl -sf "$BASE_URL/docs" >/dev/null 2>&1; then
    echo "FAIL: API server not reachable at $BASE_URL"
    echo "  Fix: docker compose up -d && sleep 5"
    exit 1
  fi
  echo "  OK: API server reachable"

  local auth_response
  auth_response=$(curl -sf -X POST "$BASE_URL/api/v1/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=cs_zhang&password=moca2024" 2>/dev/null || echo "FAIL")
  if [[ "$auth_response" == "FAIL" ]] || ! echo "$auth_response" | jq -e '.access_token' >/dev/null 2>&1; then
    echo "FAIL: Cannot authenticate demo user cs_zhang"
    echo "  Fix: uv run alembic upgrade head && uv run python scripts/seed_demo.py --reset"
    exit 1
  fi
  AGENT_TOKEN=$(echo "$auth_response" | jq -r '.access_token')
  echo "  OK: Demo user cs_zhang authenticated"

  local mgr_response
  mgr_response=$(curl -sf -X POST "$BASE_URL/api/v1/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=mgr_li&password=moca2024" 2>/dev/null || echo "FAIL")
  if [[ "$mgr_response" == "FAIL" ]] || ! echo "$mgr_response" | jq -e '.access_token' >/dev/null 2>&1; then
    echo "FAIL: Cannot authenticate demo user mgr_li"
    echo "  Fix: uv run python scripts/seed_demo.py --reset"
    exit 1
  fi
  MANAGER_TOKEN=$(echo "$mgr_response" | jq -r '.access_token')
  echo "  OK: Demo user mgr_li authenticated"

  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/agent/chat" \
    -H "Authorization: Bearer $AGENT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query":"ping","thread_id":"preflight"}' 2>/dev/null || echo "000")
  if ! echo "$http_code" | grep -qE "^(200|422|500)$"; then
    echo "FAIL: Agent chat endpoint not responding"
    echo "  Fix: Check API logs with: docker compose logs api"
    exit 1
  fi
  echo "  OK: Agent chat endpoint responding"

  echo ""
  echo "All preflight checks passed. Starting demo..."
}

require_jq
preflight

# Scenario 1: Get auth tokens
print_header "1" "Get auth tokens"
echo "Request: POST /api/v1/auth/token"
echo "Expected: support and manager JWTs are available for later scenarios"
echo ""
echo "Response:"
jq -n \
  --arg agent_token "${AGENT_TOKEN:0:20}..." \
  --arg manager_token "${MANAGER_TOKEN:0:20}..." \
  '{support_agent: "cs_zhang", manager: "mgr_li", agent_token_prefix: $agent_token, manager_token_prefix: $manager_token}'
sleep 1

# Scenario 2: Policy QA
print_header "2" "Policy QA"
echo "Request: POST /api/v1/agent/chat"
echo "Query: 平台的退款超时处理规则是什么？"
echo "Expected: evidence-backed policy answer with refund-rule citations"
echo ""
post_chat "2" "Policy QA" "平台的退款超时处理规则是什么？" "demo-thread-01"
sleep 1

# Scenario 3: Refund troubleshooting
print_header "3" "Refund troubleshooting"
echo "Request: POST /api/v1/agent/chat"
echo "Query: 订单ORD-2024-001的退款进度如何？"
echo "Expected: order/refund lookup plus policy evidence"
echo ""
post_chat "3" "Refund troubleshooting" "订单ORD-2024-001的退款进度如何？" "demo-thread-02"
sleep 1

# Scenario 4: Compensation suggestion high-risk trigger
print_header "4" "Compensation suggestion high-risk trigger"
echo "Request: POST /api/v1/agent/chat"
echo "Query: 客户投诉订单ORD-2024-002延迟发货，要求补偿600元"
echo "Expected: high-risk compensation request interrupts for approval"
echo ""
post_chat "4" "Compensation suggestion high-risk trigger" "客户投诉订单ORD-2024-002延迟发货，要求补偿600元" "demo-thread-03"
CHAT_RESPONSE="$LAST_CHAT_RESPONSE"
APPROVAL_ID=$(echo "$CHAT_RESPONSE" | jq -r '.data.approval_id // empty')
LAST_RUN_ID=$(echo "$CHAT_RESPONSE" | jq -r '.data.run_id // .data.trace_summary.run_id // empty')
if [[ -n "$APPROVAL_ID" ]]; then
  echo ""
  echo "Captured approval_id: $APPROVAL_ID"
else
  echo ""
  echo "No approval_id returned; continuing with placeholder for permission scenario."
fi
sleep 1

# Scenario 5: Permission denied
print_header "5" "Permission denied"
echo "Request: POST /api/v1/approvals/{id}/decide"
echo "Expected: 403 because cs_zhang cannot approve high-risk actions"
echo ""
PERMISSION_APPROVAL_ID="${APPROVAL_ID:-00000000-0000-0000-0000-000000000000}"
PERMISSION_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/approvals/$PERMISSION_APPROVAL_ID/decide" \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision":"approve","reason":"测试"}')
echo "Response:"
echo "$PERMISSION_RESPONSE" | jq .
sleep 1

# Scenario 6: Approval rejected
print_header "6" "Approval rejected"
echo "Request: POST /api/v1/approvals/{id}/decide"
echo "Expected: manager rejects the pending approval, resuming the agent workflow"
echo ""
if [[ -n "$APPROVAL_ID" ]]; then
  REJECT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/approvals/$APPROVAL_ID/decide" \
    -H "Authorization: Bearer $MANAGER_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"decision":"reject","reason":"补偿金额超出合理范围，建议降至200元"}')
  echo "Response:"
  echo "$REJECT_RESPONSE" | jq .
else
  echo "Skipped: no approval_id was returned by demo step 4."
fi
sleep 1

# Scenario 7: Trace query
print_header "7" "Trace query"
echo "Request: GET /api/v1/agent-runs/{run_id}/trace"
echo "Expected: timeline includes graph nodes, approval decision, and final status"
echo ""
if [[ -n "$LAST_RUN_ID" ]]; then
  TRACE_RESPONSE=$(curl -s "$BASE_URL/api/v1/agent-runs/$LAST_RUN_ID/trace" \
    -H "Authorization: Bearer $AGENT_TOKEN")
  echo "Response:"
  echo "$TRACE_RESPONSE" | jq .
  echo ""
  echo "Key fields:"
  echo "  run_id: $(echo "$TRACE_RESPONSE" | jq -r '.data.run_id // "n/a"')"
  echo "  final_status: $(echo "$TRACE_RESPONSE" | jq -r '.data.final_status // "n/a"')"
  echo "  timeline_events: $(echo "$TRACE_RESPONSE" | jq -r '.data.timeline | length // 0')"
else
  echo "Skipped: no run_id was captured from the chat scenarios."
fi

echo ""
echo "Demo complete."

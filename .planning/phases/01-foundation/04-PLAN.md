---
phase: 1
plan_id: "04"
title: "Seed Data Script + 6 Business Scenarios"
wave: 2
depends_on: ["01"]
files_modified:
  - scripts/seed_demo.py
  - scripts/__init__.py
autonomous: true
requirements: [INFR-02, TOOL-08]
---

# Plan 04: Seed Data Script + 6 Business Scenarios

<objective>
Create the deterministic seed script that populates the database with 6 high-quality Chinese business scenarios, 80+ orders, 30+ refund cases, 15+ policy documents, 12+ users across 2 tenants. Script supports --reset for idempotent re-seeding.
</objective>

<tasks>

<task id="04-01">
<title>Create seed script with reset capability and UUID v5 strategy</title>
<read_first>
- src/db/models.py
- src/db/session.py
- .planning/phases/01-foundation/01-CONTEXT.md (D-01, D-13: seed strategy)
</read_first>
<action>
Create `scripts/__init__.py` (empty).
Create `scripts/seed_demo.py`:

Structure:
```python
import argparse
import asyncio
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

MOCA_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0d02b2c3d479")

def deterministic_id(entity_type: str, key: str) -> uuid.UUID:
    return uuid.uuid5(MOCA_NAMESPACE, f"{entity_type}:{key}")

async def reset_demo_data(session):
    """Delete all data for demo tenant, then re-seed."""
    demo_tenant_id = deterministic_id("tenant", "demo")
    # DELETE cascade: audit_logs, policy_chunks, policy_documents,
    # tickets, refund_cases, orders, merchants, user_roles, users
    # WHERE tenant_id = demo_tenant_id
    # Keep roles table (shared)

async def seed_tenants(session) -> dict:
    # 2 tenants: "demo" (primary), "other" (for isolation testing)

async def seed_roles(session) -> dict:
    # 4 roles: support, manager, merchant, admin

async def seed_users(session, tenants, roles) -> dict:
    # Demo tenant: admin_user(admin), cs_zhang(support), mgr_li(manager),
    #   merchant_wang(merchant), merchant_chen(merchant)
    # Other tenant: other_admin(admin), other_support(support)
    # Total: 7+ users, passwords hashed with bcrypt
    # Default password for all demo users: "moca2024"

async def seed_merchants(session, tenants) -> dict:
    # 5 merchants in demo tenant:
    # 星河数码旗舰店 (electronics, medium risk)
    # 知味零食铺 (food, low risk)
    # 青木家居生活馆 (home, low risk)
    # 云舟在线课程 (education/virtual, low risk)
    # 南山户外用品店 (outdoor, low risk)
    # 1 merchant in other tenant for isolation testing

async def seed_orders(session, tenants, merchants) -> dict:
    # 80+ orders across 5 merchants, various statuses
    # 6 key scenario orders clearly identifiable by order_no:
    # ORD-2024-001: 未发货退款 (pending, 星河数码, 蓝牙降噪耳机 Pro, ¥599)
    # ORD-2024-002: 签收后破损 (delivered, 星河数码, 儿童学习平板 S3, ¥2999)
    # ORD-2024-003: 虚拟商品不支持退款 (completed, 云舟在线课程, Python数据分析入门课程, ¥199)
    # ORD-2024-004: 超售后期 (delivered 60+ days ago, 青木家居, 人体工学办公椅, ¥1599)
    # ORD-2024-005: 高金额需审批 (delivered, 星河数码, 高端投影仪套装, ¥8999)
    # ORD-2024-006: 多次异常退款 (delivered, 知味零食铺, 即食鸡胸肉组合装, ¥89)
    # Remaining 74+ orders: random distribution across merchants with various statuses

async def seed_refund_cases(session, tenants, orders) -> dict:
    # 30+ refund cases
    # 6 key scenarios:
    # RF-2024-001: 未按约定时间发货 (submitted, order 001)
    # RF-2024-002: 收到商品破损 (reviewing, order 002)
    # RF-2024-003: 课程内容不符合预期 (rejected, order 003)
    # RF-2024-004: 商品与描述不符 (closed, order 004, reason: 超过售后期)
    # RF-2024-005: 不想要了 (submitted, order 005, amount > threshold)
    # RF-2024-006: 重复下单 (submitted, order 006, 3rd refund from same buyer)
    # Remaining 24+: various statuses across other orders

async def seed_tickets(session, tenants, orders, refund_cases) -> dict:
    # 15+ tickets linked to orders/refund_cases
    # Key scenarios have associated tickets with Chinese summaries

async def seed_policy_documents(session, tenants) -> dict:
    # 15+ policy documents with chunks:
    # - 退款规则总则 (refund_rule, high)
    # - 未发货退款处理规范 (refund_rule, low)
    # - 签收后退款处理规范 (refund_rule, medium)
    # - 虚拟商品退款政策 (refund_rule, medium)
    # - 售后期限规定 (refund_rule, low)
    # - 高金额退款审批流程 (refund_rule, high)
    # - 异常退款风险识别指南 (high_risk_list, high)
    # - 补偿券发放标准 (compensation_sop, medium)
    # - 客服话术规范 (compensation_sop, low)
    # - 商家申诉处理流程 (appeal_process, medium)
    # - 优惠券使用规则 (coupon_rule, low)
    # - 高风险商家名单管理 (high_risk_list, high)
    # - 退款原因分类标准 (refund_rule, low)
    # - 物流异常处理指南 (refund_rule, medium)
    # - 重复退款识别规则 (high_risk_list, high)
    # Each document has 2-5 chunks with section, content (Chinese), risk_level
    # embedding column left NULL (Phase 2 fills via ingestion)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset demo data before seeding")
    args = parser.parse_args()

    async with async_session_factory() as session:
        if args.reset:
            await reset_demo_data(session)
        tenants = await seed_tenants(session)
        roles = await seed_roles(session)
        users = await seed_users(session, tenants, roles)
        merchants = await seed_merchants(session, tenants)
        orders = await seed_orders(session, tenants, merchants)
        refund_cases = await seed_refund_cases(session, tenants, orders)
        await seed_tickets(session, tenants, orders, refund_cases)
        await seed_policy_documents(session, tenants)
    print("Seed complete.")

if __name__ == "__main__":
    asyncio.run(main())
```

All IDs for key entities use deterministic_id() so they are stable across resets.
Business field identifiers (order_no, refund_case_no) are human-readable.
All Chinese content uses realistic e-commerce language.
</action>
<acceptance_criteria>
- scripts/seed_demo.py contains `argparse` with `--reset`
- scripts/seed_demo.py contains `uuid.uuid5` or `deterministic_id`
- scripts/seed_demo.py contains `MOCA_NAMESPACE`
- scripts/seed_demo.py contains `async def reset_demo_data`
- scripts/seed_demo.py contains `seed_tenants`
- scripts/seed_demo.py contains `seed_orders`
- scripts/seed_demo.py contains `seed_refund_cases`
- scripts/seed_demo.py contains `seed_policy_documents`
- scripts/seed_demo.py contains `星河数码旗舰店`
- scripts/seed_demo.py contains `蓝牙降噪耳机`
- scripts/seed_demo.py contains `未按约定时间发货`
- scripts/seed_demo.py contains at least 80 order entries (or loop generating them)
- scripts/seed_demo.py contains `ORD-2024-001`
- scripts/seed_demo.py contains `RF-2024-001`
- scripts/seed_demo.py contains `moca2024` (default password)
</acceptance_criteria>
</task>

</tasks>

<verification>
- `uv run python scripts/seed_demo.py --reset` completes without errors
- Database contains 80+ rows in orders table
- Database contains 30+ rows in refund_cases table
- Database contains 15+ rows in policy_documents table
- Database contains 7+ rows in users table
- Running `--reset` twice produces identical row counts and key entity IDs
- Key scenario orders (ORD-2024-001 through 006) exist with correct data
- Policy chunks contain Chinese content
- Two tenants exist with isolated data
</verification>

<must_haves>
- 6 fixed high-quality business scenarios with Chinese data
- 80+ orders, 30+ refund cases, 15+ policy documents
- Deterministic UUIDs via uuid5 for key entities
- --reset flag for idempotent re-seeding
- All data has tenant_id set correctly
- Second tenant exists for isolation testing
- Default password "moca2024" for all demo users
</must_haves>

<threat_model>
| Threat | Severity | Mitigation |
|--------|----------|-----------|
| Default password in production | Medium | Script only seeds demo data; README documents this is dev-only |
| Seed script deletes data | Low | Only deletes demo tenant data; other tenants untouched |
| Deterministic UUIDs predictable | Low | Demo context; production would use random UUIDs |
</threat_model>

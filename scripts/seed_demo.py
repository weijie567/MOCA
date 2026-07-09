from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select

from src.auth.jwt import hash_password
from src.db.models import (
    ActionDraft,
    ActionSafetySnapshot,
    AuditLog,
    AgentRun,
    AgentStep,
    AgentTraceEvent,
    ApprovalAssignment,
    ApprovalDecision,
    ApprovalEvent,
    ApprovalLevel,
    ApprovalRequest,
    ApprovalStep,
    CaseMemory,
    CaseWorkingContext,
    CaseWorkingContextRevision,
    ConversationMessage,
    ConversationSummary,
    ConversationThread,
    DocumentBlock,
    LongTermMemory,
    Merchant,
    MemoryTombstone,
    MemoryWriteEvent,
    Order,
    PolicyChunk,
    PolicyDocument,
    RagIngestionJob,
    RefundCase,
    Role,
    SessionMemory,
    Tenant,
    ThreadCaseLink,
    Ticket,
    ToolCallRecord,
    ToolResultRecord,
    User,
    UserRole,
)
from src.db.session import SessionLocal


MOCA_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0d02b2c3d479")


def deterministic_id(entity_type: str, key: str) -> uuid.UUID:
    return uuid.uuid5(MOCA_NAMESPACE, f"{entity_type}:{key}")


async def reset_demo_data(session) -> None:
    tenant_ids = [deterministic_id("tenant", "demo"), deterministic_id("tenant", "other")]
    user_ids = list((await session.execute(select(User.id).where(User.tenant_id.in_(tenant_ids)))).scalars().all())
    run_ids = list(
        (await session.execute(select(AgentRun.id).where(AgentRun.tenant_id.in_(tenant_ids)))).scalars().all()
    )
    approval_ids = list(
        (await session.execute(select(ApprovalRequest.id).where(ApprovalRequest.tenant_id.in_(tenant_ids))))
        .scalars()
        .all()
    )
    approval_level_ids: list[uuid.UUID] = []
    if approval_ids:
        approval_level_ids = list(
            (await session.execute(select(ApprovalLevel.id).where(ApprovalLevel.approval_request_id.in_(approval_ids))))
            .scalars()
            .all()
        )

    await session.execute(delete(SessionMemory).where(SessionMemory.tenant_id.in_(tenant_ids)))

    if run_ids:
        await session.execute(delete(ApprovalEvent).where(ApprovalEvent.run_id.in_(run_ids)))
        await session.execute(delete(AgentTraceEvent).where(AgentTraceEvent.run_id.in_(run_ids)))
        await session.execute(delete(MemoryWriteEvent).where(MemoryWriteEvent.run_id.in_(run_ids)))
        await session.execute(delete(ActionSafetySnapshot).where(ActionSafetySnapshot.run_id.in_(run_ids)))
        await session.execute(delete(AgentStep).where(AgentStep.run_id.in_(run_ids)))

    await session.execute(delete(ToolResultRecord).where(ToolResultRecord.tenant_id.in_(tenant_ids)))
    await session.execute(delete(ToolCallRecord).where(ToolCallRecord.tenant_id.in_(tenant_ids)))
    await session.execute(delete(ConversationMessage).where(ConversationMessage.tenant_id.in_(tenant_ids)))
    await session.execute(delete(ConversationSummary).where(ConversationSummary.tenant_id.in_(tenant_ids)))
    await session.execute(delete(ThreadCaseLink).where(ThreadCaseLink.tenant_id.in_(tenant_ids)))
    await session.execute(delete(ConversationThread).where(ConversationThread.tenant_id.in_(tenant_ids)))

    await session.execute(delete(CaseWorkingContextRevision).where(CaseWorkingContextRevision.tenant_id.in_(tenant_ids)))
    await session.execute(delete(CaseWorkingContext).where(CaseWorkingContext.tenant_id.in_(tenant_ids)))
    await session.execute(delete(MemoryTombstone).where(MemoryTombstone.tenant_id.in_(tenant_ids)))
    await session.execute(delete(CaseMemory).where(CaseMemory.tenant_id.in_(tenant_ids)))
    await session.execute(delete(LongTermMemory).where(LongTermMemory.tenant_id.in_(tenant_ids)))

    if approval_ids:
        await session.execute(delete(ApprovalEvent).where(ApprovalEvent.approval_request_id.in_(approval_ids)))
        await session.execute(delete(ApprovalDecision).where(ApprovalDecision.approval_request_id.in_(approval_ids)))
    if approval_level_ids:
        await session.execute(delete(ApprovalAssignment).where(ApprovalAssignment.approval_level_id.in_(approval_level_ids)))
        await session.execute(delete(ApprovalLevel).where(ApprovalLevel.id.in_(approval_level_ids)))
    if approval_ids:
        await session.execute(delete(ApprovalStep).where(ApprovalStep.approval_request_id.in_(approval_ids)))
    await session.execute(delete(ActionDraft).where(ActionDraft.tenant_id.in_(tenant_ids)))
    await session.execute(delete(ApprovalRequest).where(ApprovalRequest.tenant_id.in_(tenant_ids)))
    await session.execute(delete(AgentRun).where(AgentRun.tenant_id.in_(tenant_ids)))
    await session.execute(delete(AuditLog).where(AuditLog.tenant_id.in_(tenant_ids)))
    await session.execute(delete(RagIngestionJob).where(RagIngestionJob.tenant_id.in_(tenant_ids)))
    await session.execute(delete(PolicyChunk).where(PolicyChunk.tenant_id.in_(tenant_ids)))
    await session.execute(delete(DocumentBlock).where(DocumentBlock.tenant_id.in_(tenant_ids)))
    await session.execute(delete(PolicyDocument).where(PolicyDocument.tenant_id.in_(tenant_ids)))
    await session.execute(delete(Ticket).where(Ticket.tenant_id.in_(tenant_ids)))
    await session.execute(delete(RefundCase).where(RefundCase.tenant_id.in_(tenant_ids)))
    await session.execute(delete(Order).where(Order.tenant_id.in_(tenant_ids)))
    if user_ids:
        await session.execute(delete(UserRole).where(UserRole.user_id.in_(user_ids)))
    await session.execute(delete(User).where(User.tenant_id.in_(tenant_ids)))
    await session.execute(delete(Merchant).where(Merchant.tenant_id.in_(tenant_ids)))
    await session.execute(delete(Tenant).where(Tenant.id.in_(tenant_ids)))
    await session.commit()


async def seed_roles(session) -> dict[str, Role]:
    roles = {
        "support": Role(id=deterministic_id("role", "support"), name="support", description="Support agent"),
        "manager": Role(id=deterministic_id("role", "manager"), name="manager", description="Operations manager"),
        "merchant": Role(
            id=deterministic_id("role", "merchant"),
            name="merchant",
            description=(
                "Deprecated compatibility role; support-equivalent merchant-bound access; "
                "not a recommended new role"
            ),
        ),
        "admin": Role(id=deterministic_id("role", "admin"), name="admin", description="System admin"),
    }
    for role in roles.values():
        await session.merge(role)
    await session.flush()
    return roles


async def seed_tenants(session) -> dict[str, Tenant]:
    tenants = {
        "demo": Tenant(id=deterministic_id("tenant", "demo"), name="demo", status="active"),
        "other": Tenant(id=deterministic_id("tenant", "other"), name="other", status="active"),
    }
    for tenant in tenants.values():
        await session.merge(tenant)
    await session.flush()
    return tenants


async def seed_merchants(session, tenants: dict[str, Tenant]) -> dict[str, Merchant]:
    specs = {
        "xinghe": ("demo", "星河数码旗舰店", "electronics", "medium"),
        "zhiwei": ("demo", "知味零食铺", "food", "low"),
        "qingmu": ("demo", "青木家居生活馆", "home", "low"),
        "yunzhou": ("demo", "云舟在线课程", "education", "low"),
        "nanshan": ("demo", "南山户外用品店", "outdoor", "low"),
        "other_shop": ("other", "远航生活集合店", "general", "low"),
    }
    merchants: dict[str, Merchant] = {}
    for key, (tenant_key, name, category, risk_level) in specs.items():
        merchant = Merchant(
            id=deterministic_id("merchant", key),
            tenant_id=tenants[tenant_key].id,
            merchant_name=name,
            category=category,
            risk_level=risk_level,
        )
        await session.merge(merchant)
        merchants[key] = merchant
    await session.flush()
    return merchants


async def seed_users(
    session, tenants: dict[str, Tenant], merchants: dict[str, Merchant], roles: dict[str, Role]
) -> dict[str, User]:
    specs = [
        ("demo_admin", "demo", "admin_user", "平台管理员", "admin", None),
        ("demo_support_1", "demo", "cs_zhang", "客服张敏", "support", merchants["xinghe"].id),
        ("demo_support_2", "demo", "cs_liu", "客服刘畅", "support", merchants["zhiwei"].id),
        ("demo_support_3", "demo", "cs_sun", "客服孙悦", "support", merchants["qingmu"].id),
        ("demo_manager_1", "demo", "mgr_li", "运营经理李欣", "manager", merchants["xinghe"].id),
        ("demo_manager_2", "demo", "mgr_zhou", "风控经理周航", "manager", merchants["zhiwei"].id),
        ("demo_merchant_legacy", "demo", "merchant_legacy_wang", "兼容商家王林", "merchant", merchants["xinghe"].id),
        ("other_admin", "other", "other_admin", "异租户管理员", "admin", None),
        ("other_support", "other", "other_support", "异租户客服", "support", merchants["other_shop"].id),
    ]
    users: dict[str, User] = {}
    for key, tenant_key, username, full_name, role_name, merchant_id in specs:
        user = User(
            id=deterministic_id("user", key),
            tenant_id=tenants[tenant_key].id,
            merchant_id=merchant_id,
            username=username,
            full_name=full_name,
            password_hash=hash_password("moca2024"),
            role=role_name,
            is_active=True,
        )
        await session.merge(user)
        users[key] = user
    await session.flush()

    for key, user in users.items():
        role_name = user.role
        await session.merge(
            UserRole(
                id=deterministic_id("user_role", key),
                user_id=user.id,
                role_id=roles[role_name].id,
            )
        )
    await session.flush()
    return users


async def seed_orders(session, tenants: dict[str, Tenant], merchants: dict[str, Merchant]) -> dict[str, Order]:
    now = datetime.now(UTC)
    orders: dict[str, Order] = {}

    scenario_orders = [
        ("ORD-2024-001", "demo", "xinghe", "赵一凡", "蓝牙降噪耳机 Pro", Decimal("599.00"), "pending", 3, None),
        ("ORD-2024-002", "demo", "xinghe", "林雪", "儿童学习平板 S3", Decimal("2999.00"), "delivered", 10, 6),
        ("ORD-2024-003", "demo", "yunzhou", "周凯", "Python数据分析入门课程", Decimal("199.00"), "completed", 18, 17),
        ("ORD-2024-004", "demo", "qingmu", "王珊", "人体工学办公椅", Decimal("1599.00"), "delivered", 70, 66),
        ("ORD-2024-005", "demo", "xinghe", "陈哲", "高端投影仪套装", Decimal("8999.00"), "delivered", 8, 5),
        ("ORD-2024-006", "demo", "zhiwei", "刘元", "即食鸡胸肉组合装", Decimal("89.00"), "delivered", 12, 8),
    ]
    for (
        order_no,
        tenant_key,
        merchant_key,
        buyer,
        item,
        amount,
        status,
        created_days,
        delivered_days,
    ) in scenario_orders:
        created_at = now - timedelta(days=created_days)
        delivered_at = now - timedelta(days=delivered_days) if delivered_days is not None else None
        order = Order(
            id=deterministic_id("order", order_no),
            tenant_id=tenants[tenant_key].id,
            merchant_id=merchants[merchant_key].id,
            order_no=order_no,
            buyer_name=buyer,
            item_name=item,
            amount=amount,
            currency="CNY",
            status=status,
            created_at=created_at,
            updated_at=created_at,
            paid_at=created_at + timedelta(hours=1),
            shipped_at=created_at + timedelta(days=1) if delivered_at else None,
            delivered_at=delivered_at,
        )
        await session.merge(order)
        orders[order_no] = order

    merchant_cycle = ["xinghe", "zhiwei", "qingmu", "yunzhou", "nanshan"]
    item_cycle = ["售后保障服务包", "旅行保温杯", "营养代餐盒", "便携折叠桌", "轻量露营椅"]
    buyer_cycle = ["张伟", "李娜", "王晨", "赵敏", "孙洋", "周晨", "吴彤", "郑凯"]
    status_cycle = ["pending", "paid", "shipped", "delivered", "completed"]
    for index in range(7, 87):
        order_no = f"ORD-2024-{index:03d}"
        merchant_key = merchant_cycle[(index - 7) % len(merchant_cycle)]
        created_at = now - timedelta(days=(index % 30) + 1)
        delivered_at = created_at + timedelta(days=2) if index % 5 in (3, 4) else None
        order = Order(
            id=deterministic_id("order", order_no),
            tenant_id=tenants["demo"].id if index < 80 else tenants["other"].id,
            merchant_id=merchants[merchant_key].id if index < 80 else merchants["other_shop"].id,
            order_no=order_no,
            buyer_name=buyer_cycle[index % len(buyer_cycle)],
            item_name=item_cycle[index % len(item_cycle)],
            amount=Decimal(str(59 + (index % 12) * 25)),
            currency="CNY",
            status=status_cycle[index % len(status_cycle)],
            created_at=created_at,
            updated_at=created_at,
            paid_at=created_at + timedelta(hours=2),
            shipped_at=created_at + timedelta(days=1) if delivered_at else None,
            delivered_at=delivered_at,
        )
        await session.merge(order)
        orders[order_no] = order

    await session.flush()
    return orders


async def seed_refund_cases(session, tenants: dict[str, Tenant], orders: dict[str, Order]) -> dict[str, RefundCase]:
    refunds: dict[str, RefundCase] = {}
    scenarios = [
        ("RF-2024-001", "ORD-2024-001", "not_shipped", "未按约定时间发货", "submitted", Decimal("599.00")),
        ("RF-2024-002", "ORD-2024-002", "damaged", "收到商品破损", "reviewing", Decimal("2999.00")),
        ("RF-2024-003", "ORD-2024-003", "virtual_goods", "课程内容不符合预期", "rejected", Decimal("199.00")),
        ("RF-2024-004", "ORD-2024-004", "after_sales_expired", "商品与描述不符", "closed", Decimal("1599.00")),
        ("RF-2024-005", "ORD-2024-005", "change_mind", "不想要了", "submitted", Decimal("8999.00")),
        ("RF-2024-006", "ORD-2024-006", "duplicate_order", "重复下单", "submitted", Decimal("89.00")),
    ]
    for case_no, order_no, reason_code, reason_text, status, amount in scenarios:
        order = orders[order_no]
        refund = RefundCase(
            id=deterministic_id("refund_case", case_no),
            tenant_id=order.tenant_id,
            order_id=order.id,
            refund_case_no=case_no,
            reason_code=reason_code,
            reason_text=reason_text,
            status=status,
            requested_amount=amount,
            approved_amount=amount if status == "refunded" else None,
            created_at=order.created_at + timedelta(days=1),
            updated_at=order.created_at + timedelta(days=1),
        )
        await session.merge(refund)
        refunds[case_no] = refund

    status_cycle = ["submitted", "reviewing", "approved", "rejected", "closed"]
    reason_cycle = [
        ("logistics_delay", "物流异常"),
        ("damaged", "外包装破损"),
        ("wrong_item", "商品与描述不符"),
        ("quality_issue", "商品存在质量问题"),
    ]
    order_numbers = [order_no for order_no in orders if order_no.startswith("ORD-2024-0")][6:30]
    for index, order_no in enumerate(order_numbers, start=7):
        reason_code, reason_text = reason_cycle[index % len(reason_cycle)]
        order = orders[order_no]
        case_no = f"RF-2024-{index:03d}"
        refund = RefundCase(
            id=deterministic_id("refund_case", case_no),
            tenant_id=order.tenant_id,
            order_id=order.id,
            refund_case_no=case_no,
            reason_code=reason_code,
            reason_text=reason_text,
            status=status_cycle[index % len(status_cycle)],
            requested_amount=order.amount,
            approved_amount=order.amount if index % 5 == 2 else None,
            created_at=order.created_at + timedelta(days=1),
            updated_at=order.created_at + timedelta(days=1),
        )
        await session.merge(refund)
        refunds[case_no] = refund

    await session.flush()
    return refunds


async def seed_tickets(session, orders: dict[str, Order], refunds: dict[str, RefundCase]) -> dict[str, Ticket]:
    tickets: dict[str, Ticket] = {}
    key_cases = [
        ("TK-2024-001", "ORD-2024-001", "RF-2024-001", "chat", "open", "用户催促发货并要求退款"),
        ("TK-2024-002", "ORD-2024-002", "RF-2024-002", "phone", "in_progress", "签收后反馈屏幕碎裂"),
        ("TK-2024-003", "ORD-2024-003", "RF-2024-003", "chat", "closed", "课程类订单退款争议"),
        ("TK-2024-004", "ORD-2024-004", "RF-2024-004", "chat", "closed", "售后期外申请退款"),
        ("TK-2024-005", "ORD-2024-005", "RF-2024-005", "phone", "open", "高金额退款需升级审核"),
        ("TK-2024-006", "ORD-2024-006", "RF-2024-006", "chat", "open", "用户出现重复退款行为"),
    ]
    for ticket_no, order_no, refund_case_no, channel, status, summary in key_cases:
        order = orders[order_no]
        refund = refunds[refund_case_no]
        ticket = Ticket(
            id=deterministic_id("ticket", ticket_no),
            tenant_id=order.tenant_id,
            order_id=order.id,
            refund_case_id=refund.id,
            ticket_no=ticket_no,
            channel=channel,
            status=status,
            summary=summary,
            messages=[
                {"speaker": "user", "content": summary, "created_at": order.created_at.isoformat()},
                {
                    "speaker": "agent",
                    "content": "已记录问题，正在核实订单与退款信息。",
                    "created_at": datetime.now(UTC).isoformat(),
                },
            ],
        )
        await session.merge(ticket)
        tickets[ticket_no] = ticket

    refund_items = list(refunds.items())[6:15]
    for index, (refund_case_no, refund_case) in enumerate(refund_items, start=7):
        ticket_no = f"TK-2024-{index:03d}"
        order = next(order for order in orders.values() if order.id == refund_case.order_id)
        ticket = Ticket(
            id=deterministic_id("ticket", ticket_no),
            tenant_id=refund_case.tenant_id,
            order_id=refund_case.order_id,
            refund_case_id=refund_case.id,
            ticket_no=ticket_no,
            channel="chat" if index % 2 else "phone",
            status="open" if index % 3 else "closed",
            summary=f"关于 {refund_case.reason_text} 的跟进工单",
            messages=[
                {
                    "speaker": "user",
                    "content": f"订单 {order.order_no} 希望尽快处理退款。",
                    "created_at": order.created_at.isoformat(),
                },
                {
                    "speaker": "agent",
                    "content": "已同步到退款队列，等待复核。",
                    "created_at": datetime.now(UTC).isoformat(),
                },
            ],
        )
        await session.merge(ticket)
        tickets[ticket_no] = ticket

    await session.flush()
    return tickets


async def seed_policy_documents(session, tenants: dict[str, Tenant]) -> dict[str, PolicyDocument]:
    documents: dict[str, PolicyDocument] = {}
    docs = [
        ("refund_general", "退款规则总则", "refund_rule", "high"),
        ("not_shipped", "未发货退款处理规范", "refund_rule", "low"),
        ("damaged_after_delivery", "签收后退款处理规范", "refund_rule", "medium"),
        ("virtual_goods", "虚拟商品退款政策", "refund_rule", "medium"),
        ("after_sales_period", "售后期限规定", "refund_rule", "low"),
        ("high_amount_approval", "高金额退款审批流程", "refund_rule", "high"),
        ("abnormal_refunds", "异常退款风险识别指南", "high_risk_list", "high"),
        ("coupon_compensation", "补偿券发放标准", "compensation_sop", "medium"),
        ("service_tone", "客服话术规范", "compensation_sop", "low"),
        ("merchant_appeal", "商家申诉处理流程", "appeal_process", "medium"),
        ("coupon_rules", "优惠券使用规则", "coupon_rule", "low"),
        ("high_risk_merchants", "高风险商家名单管理", "high_risk_list", "high"),
        ("refund_reason_taxonomy", "退款原因分类标准", "refund_rule", "low"),
        ("logistics_abnormal", "物流异常处理指南", "refund_rule", "medium"),
        ("duplicate_refund_rule", "重复退款识别规则", "high_risk_list", "high"),
    ]
    today = date.today()
    for index, (key, title, doc_type, risk_level) in enumerate(docs, start=1):
        content = f"{title}：用于客服与运营处理相关退款场景，要求以证据和租户权限为前提。"
        document = PolicyDocument(
            id=deterministic_id("policy_document", key),
            tenant_id=tenants["demo"].id,
            doc_key=key,
            doc_type=doc_type,
            title=title,
            effective_date=today - timedelta(days=index),
            risk_level=risk_level,
            version=1,
            content=content,
        )
        await session.merge(document)
        documents[key] = document
        for chunk_index, section in enumerate(["适用范围", "处理规则"], start=1):
            chunk = PolicyChunk(
                id=deterministic_id("policy_chunk", f"{key}:{chunk_index}"),
                tenant_id=tenants["demo"].id,
                doc_id=document.id,
                chunk_id=f"{key}-{chunk_index}",
                section=section,
                content=f"{title} - {section}：请结合订单、退款单、工单证据进行判断。",
                risk_level=risk_level,
                effective_date=document.effective_date,
                embedding=None,
            )
            await session.merge(chunk)
    await session.flush()
    return documents


async def seed_all(reset: bool) -> None:
    async with SessionLocal() as session:
        if reset:
            await reset_demo_data(session)
        roles = await seed_roles(session)
        tenants = await seed_tenants(session)
        merchants = await seed_merchants(session, tenants)
        await seed_users(session, tenants, merchants, roles)
        orders = await seed_orders(session, tenants, merchants)
        refunds = await seed_refund_cases(session, tenants, orders)
        await seed_tickets(session, orders, refunds)
        await seed_policy_documents(session, tenants)
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic MOCA demo data")
    parser.add_argument("--reset", action="store_true", help="Reset demo tenants before seeding")
    args = parser.parse_args()
    asyncio.run(seed_all(reset=args.reset))


if __name__ == "__main__":
    main()

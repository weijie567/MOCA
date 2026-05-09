# Phase 1: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 01-foundation
**Areas discussed:** Seed 数据策略, Demo 鉴权体验, Python 工具链, API 语言策略, 数据库边界, 多租户, RBAC, 审计日志, Docker Compose, 错误格式, 测试门槛, Seed 重置

---

## Seed 数据策略

| Option | Description | Selected |
|--------|-------------|----------|
| 固定场景为主 + 随机填充 | 固定 5-10 个典型场景，每个有完整闭环，保证演示走通 | ✓ |
| 纯随机生成 | Faker 生成，数据量大但不保证业务逻辑闭环 | |
| 纯手写 fixtures | 全部手写 JSON/YAML，数据量小但每条有明确业务含义 | |

**User's choice:** 固定场景为主 + 随机填充 → 后续明确为 6 个固定场景，Phase 1 不用 Faker
**Notes:** 用户提供了具体场景列表、商家名、商品名、退款原因示例。决定 Phase 1 全部手写，Phase 2/3 再加 Faker。

---

## Seed 场景数量

| Option | Description | Selected |
|--------|-------------|----------|
| 5 个场景 | 覆盖退款争议典型场景 | ✓ (后调整为6) |
| 8-10 个场景 | 更多边缘 case | |
| 3 个场景 | 最小可演示 | |

**User's choice:** 5 个场景（推荐）→ 用户后续补充为 6 个具体场景
**Notes:** 用户给出了 6 个具体场景定义

---

## Seed 数据语言

| Option | Description | Selected |
|--------|-------------|----------|
| 全中文 | 商家名、商品名、退款原因全中文，贴近真实平台 | ✓ |
| 中英混合 | 字段名英文，业务内容中英混合 | |

**User's choice:** 全中文（推荐）

---

## Demo 鉴权体验

| Option | Description | Selected |
|--------|-------------|----------|
| 预生成固定 token | seed 时生成固定 JWT，写入 .env.example | |
| Demo token 签发接口 | POST /api/v1/auth/demo-token，传入用户名获取 JWT | ✓ |
| 两者结合 | 有签发接口，同时 README 给出预生成 token | |

**User's choice:** Demo token 签发接口 → 后续明确为完整 login 流程为主，demo-token 仅限开发环境
**Notes:** 用户提供了 10 点详细鉴权设计要求，优先企业级实践

---

## Demo 角色

| Option | Description | Selected |
|--------|-------------|----------|
| 3 个角色 | support, manager, merchant | |
| 4 个角色（加 admin） | support, manager, merchant, admin | ✓ |

**User's choice:** 4 个角色（加 admin）

---

## Python 包管理器

| Option | Description | Selected |
|--------|-------------|----------|
| uv | 最新一代，极快，原生 pyproject.toml | ✓ |
| poetry | 成熟稳定，依赖解析较慢 | |
| pip + requirements.txt | 最简单，缺少 lock 文件 | |

**User's choice:** uv（推荐）

---

## Python 版本

| Option | Description | Selected |
|--------|-------------|----------|
| Python 3.12 | 最新稳定版，全特性支持 | ✓ |
| Python 3.11 | 更保守，兼容性更广 | |

**User's choice:** Python 3.12（推荐）

---

## Linter/Formatter

| Option | Description | Selected |
|--------|-------------|----------|
| ruff（lint + format） | 极快，配置简单，社区主流 | ✓ |
| black + isort + flake8 | 经典组合，配置分散 | |

**User's choice:** ruff（lint + format）

---

## API 语言策略

| Option | Description | Selected |
|--------|-------------|----------|
| 接口英文 + 数据中文 | 字段名/endpoint/错误码英文，业务数据中文 | ✓ |
| 全英文 | 包括业务数据 | |
| 全中文 | 字段名也中文/拼音 | |

**User's choice:** 接口英文 + 数据中文（推荐）

---

## 错误信息语言

| Option | Description | Selected |
|--------|-------------|----------|
| 错误信息英文 | code 和 message 都英文，前端负责 i18n | ✓ |
| 错误信息中文 | message 中文，演示更直观 | |

**User's choice:** 错误信息英文（推荐）
**Notes:** 用户后续示例中写了中文 message，经确认统一为英文

---

## 扩展决策（用户主动提供）

用户在最后一轮一次性提供了 8 个额外决策点的完整方案，涵盖数据库边界、多租户、RBAC、审计日志、Seed 重置、错误格式、Docker Compose、测试门槛。这些决策直接采纳并记录在 CONTEXT.md 中。

---

## Claude's Discretion

- pytest 具体插件选择
- Alembic migration 组织方式
- Repository base class 实现模式
- Docker 镜像 base image 选择
- Tool 返回具体字段设计

## Deferred Ideas

- Faker 批量数据生成 — Phase 2/3
- Redis 实际使用 — Phase 2+
- 完整审计链路 — Phase 4
- 动态 RBAC — v2
- Agent runtime 表 — Phase 3

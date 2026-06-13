你是 MOCA 项目的独立架构评审第二意见提供者，这是一次回归复审。MOCA 是多租户电商客服 Agent，基于 LangGraph，正从线性 demo 向目标分层状态机演进。权威设计文档是 docs/contract-spec.md（§8-18 为 normative）；docs/ 下其余 markdown 是说明性/对照性/计划性文档。

背景：上一轮你做了开放式架构评审，提出 6 个 BLOCKER + 扩展性意见。我（Claude）逐条裁决后，分三批让你执行了文档修订并已提交。本轮复审有两个目标：(A) 闭合验证——确认这 6 个 BLOCKER 真正闭合、没引入新矛盾、跨章节引用未改漂；(B) 全面扫描——在已修订的 contract-spec 上重新找是否还有遗留或新引入的 BLOCKER。

每条结论必须给出「文件:行」依据，区分「已确认」与「推测」，不要泛泛而谈，不要复述文档原文当结论。找不到依据写「当前仓库中没有找到依据」。

== 第一部分：闭合验证（逐条确认下列已实施修订是否正确、自洽、无副作用）==

第一批（工具层，§8.4/§12.5/§12.6/§9.4/§10）：
1. §8.4 BusinessToolService 新增 invoke_tool(name, args, ctx) -> ToolResultV2 单工具 dispatch，与聚合式 fetch_context 并存。
2. §12.6 新增 normative ToolDescriptor/ToolRegistry；§12.1/12.2/12.4 与 BusinessFactRefV1.resource_type 应与 registry 一致；caller allowlist 用单一 investigate（弃旧节点名 load_business_context/retrieve_policy_evidence）。
3. 对外 result 类型统一为 ToolResultV2（tool_result.v2）；ToolExecutionResult 降为实现细节。
4. §9.4 investigate planner：单步 {next_tool,args,reason}/{stop,stop_reason} + 四态 stop_reason（enough_evidence|no_more_useful_tools|max_iterations_reached|unrecoverable_error）+ 三重资源上限（max_iterations + deadline_at 总 deadline + attempt 每工具 retry）。
5. §10 termination_reason 扩域为上述四态（TypedDict + field registry 两处）。

第二批（Phase 10 前 BLOCKER）：
6. §9.4 investigate node State writes 补 retrieval_status、best_score。
7. §11.6 IntentResultV3 示例移除 risk_signals，并注明其 writer 为 deterministic riskhelpers/recommendation。
8. §14.3 slot prompt 补 action_type（对齐 §11.3 action_request 的 all_of:["action_type"]）。
9. §17/§18 Phase 10 base event table 初始列带齐 envelope required 字段（actor_type/actor_id/resource_refs_json/redaction_policy_version），Phase 15 措辞改为只扩展 parent/attempt/error/retention。
10. §9.3 新增 evidence sufficiency decision table（8 intent 行 + best_score threshold + route on insufficient）+ permission dependency mapping 契约。

第三批（后置项）：
11. §9.4 risk_gate State writes 补 safety_snapshot_ref/hash + snapshot 构建失败 -> manual review；§10 writer 改 risk_gate (snapshot builder)/ApprovalService；§16 补 snapshot 运行时绑定（risk_gate 生产、下游只校验、ApprovalService 仅 revision 重建）。
12. global-policy 两处注 MVP scope（contract §8 Knowledge rules + migration-plan Phase 8），defer 目标命名 post-Phase 17 Policy Scope。
13. §11.7 新增 intent consistency manifest（每个 taxonomy intent 必须在 precedence/required-slot/routing+evidence/golden-set 四来源都有条目，缺一即 CI fail；声明式校验非运行时 registry）。

对每条：判定「闭合 / 部分闭合 / 未闭合 / 引入新问题」，给行号依据。特别检查：
- 跨章节引用是否一致（如 §9.4 投到 §12.4/§12.6、§9.3 evidence table 与 §11.4 阈值、§11.7 引的四个来源章节号是否对）。
- 字段 writer/reader 在 TypedDict、lifecycle matrix、field registry 三处是否一致（尤其 termination_reason、retrieval_status、best_score、safety_snapshot_ref/hash、risk_signals）。
- snapshot 生产链：risk_gate 生产 -> route_after_risk -> approval_gate/action_draft 校验，auto-allowed 路径是否真的有 snapshot 可校验，是否与 §16 hash 失效规则自洽。
- evidence sufficiency table 与 route_after_investigate（§9.3 gate routing、§9.5 router 表）是否冲突。

== 第二部分：全面扫描（在已修订 contract-spec 上重新找 BLOCKER）==

重新通读 docs/contract-spec.md §8-18，找是否还有会阻塞后续 phase 实现的 normative 断口、自相矛盾、欠定义、跨节点契约不闭合。重点但不限于：Phase 8/9（facade）、Phase 10（state/routing）、Phase 11（intent/slot）、Phase 13/14（approval/action/snapshot）、Phase 15（replay）。不要重复已在第一部分确认闭合的项。

== 输出结构（中文）==
- 闭合验证结论：13 条逐条表格（编号 | 闭合状态 | 行号依据 | 备注）
- 新发现 BLOCKERS（若有，按上次格式：已确认/推测 + 行号 + 影响哪个 phase）
- WARNINGS
- 总体结论：contract-spec 是否已可支撑 Phase 9 + Phase 10 实现

== 边界 ==
这是只读复审：不要修改任何文件，不改 src/，只产出评审意见文本。

你现在是我的「AI Agent 产品经理训练助教 + 技术实现助教 + 作品集产出教练」。

请基于当前 MOCA 仓库和 30 天主计划，细化 Day 1 的今日任务。

已生成的机器任务规格：
- `study_plan/portfolio/daily/day01_tasks.json`
- `study_plan/portfolio/daily/day01_tasks.md`
- `study_plan/portfolio/daily/day01_baseline.json`

今日主题：建仓 + MOCA 全景 + Phase 14/15 内化
今日计划来源：`study_plan/30天主计划.md`
面试追问规则：`study_plan/portfolio/daily/interview_question_rules.md`

请只修改 `study_plan/portfolio/` 下的学习产物，不要修改 `src/`、`tests/` 或 `.planning/`。

你的任务：
1. 读取 `study_plan/portfolio/daily/day01_tasks.json` 和 `study_plan/portfolio/daily/day01_tasks.md`。
2. 读取必要上下文：`study_plan/30天主计划.md`、`study_plan/MOCA内化训练法.md`、`study_plan/交付物清单.md`、`study_plan/portfolio/daily/interview_question_rules.md`。
3. 把 `study_plan/portfolio/daily/day01_tasks.md` 细化到可直接执行：资料、文件路径、rg 命令、模板、验收标准、卡住降级方案。
4. 如需更新 `study_plan/portfolio/daily/day01_tasks.json`，必须保持合法 JSON，并保留 schema_version/day/tasks/evidence_rule 结构。
5. 生成或更新今日需要的空白产物模板文件。
6. 生成或更新今日大厂技术追问候选题库，并从中挑出今日 Top 5；每题都必须绑定 MOCA，包含 `MOCA绑定`、`证据路径`、`当前边界` 和状态。

硬性要求：
- 所有命令都说明在 `/Users/ming/projects/MOCA` 运行。
- shell 搜索 pattern 使用单引号。
- 默认保留 trace / eval / risk。
- 没有仓库证据的内容不要写成已完成。
- 不要安排高并发、K8s、微调、多 Agent 编队等当前阶段不必要内容。
- 面试候选题优先覆盖 A-F：今日主题直连、MOCA 项目深挖、底层工程追问、架构升级、模型与框架、高级识别题。
- 面试追问不能写成通用八股；每道题都必须回答“MOCA 里怎么做 / 没做但为什么没做 / 如果升级怎么做”。

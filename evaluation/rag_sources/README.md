# RAG 评测语料 V1

这组 fixture 不修改 `data/policies/` 中的 demo 数据。三份 Markdown 是每个政策族的 source of truth；每份 source 生成一个数字 PDF 和一个无文字层的扫描 PDF，供 parser parity 与 retrieval parity 使用。

## 主题选择

| 政策族 | 覆盖能力 | 主要干扰点 |
| --- | --- | --- |
| 国内普通实物订单退款与退货 | 七天无理由、质量问题、已发货仅退款、运费和自动退款 | 7/30 日、24/48 小时、500/3000 元、高风险订单 |
| 质量问题与补偿审批 | 证据分级、维修/换新/退款、批量质量事件、审批链 | 48 小时、30 日、10%-30%、500/2000/5000 元边界 |
| 跨境订单与数字商品退款例外 | 清关、税费、汇率、物流异常、发码/激活/消费状态 | 15-30 日、72 小时、1000 美元、已激活与部分使用 |

每个主题都是 5 页左右的完整政策，不是重复句子的长度填充；内容包含多级标题、列表、表格、例外、流程、场景示例和审计字段。

## Canonical lineage 与原子 reconciliation

Markdown 是三个政策族唯一声明的 source of truth。2026-08-10 的仓库历史核对确认：fixture 家族在 `660a571`（完整 commit `660a571d260d1e9a4afa9547b257426726b62e0d`，`feat(eval): add RAG quality benchmark corpus`）一次性引入，三个 Markdown 路径都没有第二个历史版本。因此当前 checked-in Markdown 即 canonical bytes；不存在一个可从 Git 恢复、且能匹配 manifest stale hash 的更早 Markdown revision。

核对命令与结果：

```text
$ git log --all --oneline -- evaluation/rag_sources/fixtures
660a571 feat(eval): add RAG quality benchmark corpus

$ git log --all --format='%H %s' -- evaluation/rag_sources/fixtures/refund_eligibility_and_return/refund_eligibility_and_return.md
660a571d260d1e9a4afa9547b257426726b62e0d feat(eval): add RAG quality benchmark corpus
$ git log --all --format='%H %s' -- evaluation/rag_sources/fixtures/quality_compensation_and_approval/quality_compensation_and_approval.md
660a571d260d1e9a4afa9547b257426726b62e0d feat(eval): add RAG quality benchmark corpus
$ git log --all --format='%H %s' -- evaluation/rag_sources/fixtures/cross_border_and_digital_goods/cross_border_and_digital_goods.md
660a571d260d1e9a4afa9547b257426726b62e0d feat(eval): add RAG quality benchmark corpus
```

`git show 660a571:<Markdown path> | shasum -a 256` 与当前文件得到同一组 canonical hash；Task 1 的流式 SHA-256 核对同时证明 manifest 中只有 Markdown 三项 stale、六个 PDF 项仍匹配其当前 bytes：

| 政策族 | manifest stale Markdown SHA-256 | current / `660a571` canonical Markdown SHA-256 |
| --- | --- | --- |
| `eval_refund_eligibility_and_return` | `b59685b3f1594906284c362b5af4ab8b3df8132a9bed6a158245406723dfee99` | `81654bb2e4adbc7b95b41823c90d77754785c4243d60fed2b382ec7fae9ce8c7` |
| `eval_quality_compensation_and_approval` | `e7fb86822ea99f96139b89d3a14f498588fba69e4625b8d374f9f02db4c8eb5e` | `f7c115028dcd20da2c7e0b0033612b4bf5857c006408131b3a1bf63f5eb96cea` |
| `eval_cross_border_and_digital_goods` | `c4bd19adcc696104fd56a1531da1f3b31d1b301f6f9fb0c471374f2d19fe0c83` | `8641827819922c734f3baebc913b009c70e41fe37ca551380e24cebcf19e5cb9` |

manifest 自引入 commit 起即与其同一 commit 中的 Markdown bytes 不一致，所以只改三条 SHA 的 **hash-only refresh** 不构成 lineage reconciliation，也不得用于放行 evaluator。批准的原子路线是：保留当前 canonical Markdown；使用锁定的 generator、字体和工具链重新生成全部三个 digital PDF 与三个 scanned PDF；对六个 PDF 做页数、文字层、heading/anchor/table 顺序的自动检查和全页视觉检查；最后一次性重写完整 manifest 的 generator metadata 与 Markdown/PDF 全部九条 hash。任一步未通过时，整个 3/9 家族继续 fail closed。

## 文件布局

```text
evaluation/rag_sources/
  README.md
  build_fixtures.py
  format_parity_manifest.jsonl
  fixtures/
    refund_eligibility_and_return/
      refund_eligibility_and_return.md
      refund_eligibility_and_return.digital.pdf
      refund_eligibility_and_return.scanned.pdf
    quality_compensation_and_approval/
      ...
    cross_border_and_digital_goods/
      ...
```

## 重新生成

在仓库根目录执行：

```bash
uv run --with reportlab python evaluation/rag_sources/build_fixtures.py
```

脚本会重新生成 6 个 PDF，并更新 `format_parity_manifest.jsonl` 的 SHA-256、页数和文字层统计。扫描 PDF 使用 200 DPI 灰度页面生成，不含 PDF 文字层；数字 PDF 保留可选文字层和表格。

## 使用边界

- Parser parity：直接读取 manifest 中同一 `doc_key` 的三个 variant，不需要 tenant。
- Retrieval parity：固定一个评测 tenant，三个 variant 分三轮摄取；每轮开始前清空本轮 RAG 数据，不能把同一政策的三个等价版本同时入库。
- Mixed retrieval：从每个政策族只选择一个 variant，再与后续扩充的背景政策合并。当前仓库的 `data/policies/` 仍是 demo/smoke corpus，不能和本目录的同名逻辑政策在同一轮重复入库。

当前 manifest 是格式等价组，不会自动改写现有 `evaluation/golden/rag_cases.jsonl`。下一步建立混合检索组时，应新增独立 manifest 和 gold query 集，避免污染现有 demo 回归基线。

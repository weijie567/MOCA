# RAG 评测语料 V1

这组 fixture 不修改 `data/policies/` 中的 demo 数据。三份 Markdown 是每个政策族的 source of truth；每份 source 生成一个数字 PDF 和一个无文字层的扫描 PDF，供 parser parity 与 retrieval parity 使用。

## 主题选择

| 政策族 | 覆盖能力 | 主要干扰点 |
| --- | --- | --- |
| 国内普通实物订单退款与退货 | 七天无理由、质量问题、已发货仅退款、运费和自动退款 | 7/30 日、24/48 小时、500/3000 元、高风险订单 |
| 质量问题与补偿审批 | 证据分级、维修/换新/退款、批量质量事件、审批链 | 48 小时、30 日、10%-30%、500/2000/5000 元边界 |
| 跨境订单与数字商品退款例外 | 清关、税费、汇率、物流异常、发码/激活/消费状态 | 15-30 日、72 小时、1000 美元、已激活与部分使用 |

每个主题都是 5 页左右的完整政策，不是重复句子的长度填充；内容包含多级标题、列表、表格、例外、流程、场景示例和审计字段。

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

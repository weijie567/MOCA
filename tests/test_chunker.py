from src.rag.chunker import chunk_markdown
from src.rag.embedding_tokenizer import EmbeddingTokenCounter, load_embedding_tokenizer_config
from src.rag.parsers.base import ParsedBlock
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler


def test_basic_heading_split():
    markdown = """
## 七天无理由
消费者签收后七天内可申请退货退款。
## 仅退款
商家已发货时，客服需要先核实物流状态。
### 破损补偿
商品破损需要用户上传图片凭证。
"""

    chunks = chunk_markdown(markdown, "refund_policy")

    assert [chunk.section for chunk in chunks] == ["七天无理由", "仅退款", "破损补偿"]
    assert [chunk.content for chunk in chunks] == [
        "消费者签收后七天内可申请退货退款。",
        "商家已发货时，客服需要先核实物流状态。",
        "商品破损需要用户上传图片凭证。",
    ]


def test_stable_chunk_ids():
    markdown = """
## 退款时效
退款审核通过后，系统应在两个工作日内原路退回。
## 商家举证
商家拒绝退款时，需要上传物流签收或商品完好凭证。
"""

    first = chunk_markdown(markdown, "refund_policy")
    second = chunk_markdown(markdown, "refund_policy")

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.chunk_id for chunk in first] == ["refund_policy_000", "refund_policy_001"]
    assert all(chunk.doc_key == "refund_policy" for chunk in first)


def test_oversized_section_split():
    markdown = "## 退款规则\n" + ("用户申请退款时客服应核实订单状态。" * 120)

    chunks = chunk_markdown(markdown, "refund_policy")

    assert len(chunks) > 1
    assert all(chunk.chunk_id.startswith("refund_policy_000_part_") for chunk in chunks)
    assert [chunk.part_index for chunk in chunks] == list(range(1, len(chunks) + 1))


def test_overlap_within_section():
    sentence = "用户申请退款时客服应核实订单状态并记录处理结论。"
    markdown = "## 售后 SOP\n" + (sentence * 120)

    chunks = chunk_markdown(markdown, "refund_sop", max_chars=900, target_chars=700, overlap_chars=100)

    assert len(chunks) > 1
    assert chunks[0].content[-100:] == chunks[1].content[:100]
    assert all(chunk.section == "售后 SOP" for chunk in chunks)


def test_intro_section():
    markdown = """
退款知识库用于客服判断风险动作。

## 退款入口
客服从工单详情进入退款审核。
"""

    chunks = chunk_markdown(markdown, "refund_faq")

    assert chunks[0].section == "intro"
    assert chunks[0].content == "退款知识库用于客服判断风险动作。"
    assert chunks[1].section == "退款入口"


def test_empty_sections_skipped():
    markdown = """
## 空规则

## 有效规则
商家同意后才可以执行高风险退款动作。
"""

    chunks = chunk_markdown(markdown, "refund_policy")

    assert len(chunks) == 1
    assert chunks[0].section == "有效规则"


def test_chinese_character_counting():
    markdown = "## 长规则\n" + ("退" * 1201)

    chunks = chunk_markdown(markdown, "refund_policy", max_chars=1200, target_chars=800, overlap_chars=100)

    assert len(chunks) == 2
    assert all(len(chunk.content) <= 1200 for chunk in chunks)


def test_sentence_boundary_split():
    first = "用户申请退款时，客服先核实订单状态。"
    second = "如果订单已经发货，客服必须查看物流轨迹！"
    third = "如果证据不足，需要转人工复核？"
    markdown = "## 边界规则\n" + first * 35 + second * 35 + third * 35

    chunks = chunk_markdown(markdown, "refund_policy", max_chars=900, target_chars=650, overlap_chars=100)

    assert len(chunks) > 1
    assert chunks[0].content.endswith(("。", "！", "？"))


def test_max_chars_enforced():
    markdown = "## 最大长度\n" + ("用户退款需要核实凭证。" * 140)

    chunks = chunk_markdown(markdown, "refund_policy")

    assert chunks
    assert all(len(chunk.content) <= 1200 for chunk in chunks)


def test_long_no_punctuation():
    body = "退款规则 " * 700
    markdown = "## 无标点规则\n" + body

    chunks = chunk_markdown(markdown, "refund_policy", max_chars=1200, target_chars=800, overlap_chars=100)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 1200 for chunk in chunks)


def test_token_aware_chunk_ids_are_stable_for_identical_source_and_config():
    block = ParsedBlock(
        source_block_id="refund_policy:paragraph:0000",
        block_index=0,
        block_type="paragraph",
        text="用户申请退款时客服应核实订单状态。" * 300,
        normalized_text="用户申请退款时客服应核实订单状态。" * 300,
        source_type="policy_markdown",
        parser_name="markdown",
        parser_version="21.01",
        page_number=None,
        box=None,
    )
    assembler = PolicyEmbeddingInputAssembler(counter=EmbeddingTokenCounter(load_embedding_tokenizer_config()))

    first = assembler.assemble(blocks=(block,), doc_key="refund_policy", title="退款政策")
    second = assembler.assemble(blocks=(block,), doc_key="refund_policy", title="退款政策")

    assert first == second
    assert [item.chunk_id for item in first] == [item.chunk_id for item in second]

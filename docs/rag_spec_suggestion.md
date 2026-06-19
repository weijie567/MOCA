# MOCA RAG 架构评估与改进建议

## 总体判断

你的方向是对的，而且不是“抄框架”，而是在吸收生产级 RAG 的通用做法后，按 MOCA 现有的契约、Agent 结构和 Postgres 技术栈做本地化设计。这种做法比直接把某个开源项目整体搬进来更稳，因为 RAGFlow、Onyx、Dify、Haystack 分别强调的是不同层面的能力：RAGFlow 更偏文档理解与解析，Onyx 更偏可运营的索引与同步流水线，Dify 更偏中小规模可落地的知识库工作流，Haystack 更偏清晰的组件边界与流水线组合。你的 spec 也已经明确了类似取舍：PostgreSQL 仍是 canonical source of truth，当前阶段主线是 PostgreSQL hybrid retrieval，Vespa 只作为未来可替换 backend，Business Data QA 不走 RAG 猜测，而 hallucination control 也被定义成 evidence-chain 工程，而不是单纯 prompt 技巧。这个总体判断，与外部项目的成熟经验是同向的。fileciteturn0file0 fileciteturn0file1 citeturn22view0turn9view0turn6view0turn11view0turn11view1turn4view7

更具体地说，你已经抓住了生产级客服 RAG 最关键的四件事：一是把 OCR、layout、table、page/bbox 提前到 ingestion 层，而不是等到“切 chunk 之后”再补；二是把检索定义成 dense + sparse + fuzzy 的多路召回，而不是单路向量检索；三是把 citation 从“展示用链接”提升为 evidence contract；四是把订单、退款、账户等业务事实从政策检索中剥离出去，强制走 tool/API/SQL。对于客服场景，这四点比是否一开始接入 Vespa 更重要。fileciteturn0file0 fileciteturn0file1 citeturn22view0turn9view0turn6view0turn19academia1turn18academia1turn19academia2

## 借鉴点里最值得保留的部分

你从 RAGFlow / deepdoc 借来的，不应是某个具体包，而是“文档先被理解，再被检索”这个前提。RAGFlow 仓库中，`deepdoc` 被明确拆成 `vision` 和 `parser` 两部分；README 直接把 OCR、layout recognition、table structure recognition、表格自动旋转，以及 PDF parser 输出的 page number、rectangular positions、table contents、figure captions 等列成核心能力。也就是说，deepdoc 的价值不在于“一个特殊 OCR 库”，而在于把 PDF/扫描件/复杂版式理解成结构化中间层。你在 spec 里引入 `DocumentBlock`、`page_number`、`bbox_json`、`ocr_confidence`、`table_json`、`parser_version`，本质上正是在落实这个思想。这个方向不但合理，而且对强 citation 的 policy QA 是必要前提。citeturn22view0 fileciteturn0file0

你从 Onyx 借来的，是“索引不是一个函数调用，而是一条可审计流水线”的意识，这也很到位。Onyx 官方仓库把标准部署模式与轻量模式明确区分；标准模式额外包含 vector + keyword index、后台队列和 worker、连接器同步、推理服务、缓存和 blob store，并且它也强调 RBAC 与 query history 这类企业治理能力。对 MOCA 来说，最应该吸收的不是它的完整部署复杂度，而是“索引写入、同步、失败恢复、权限和审计必须是系统能力”的标准。你在 spec 中把 ingestion 拆到 parser / OCR / cleaning / chunking / embedding / indexing，并规划 `SearchBackend` 抽象，已经在沿着这个方向走。citeturn9view0 fileciteturn0file0

你从 Dify 借来的，是“先做一套能跑通、可测试、可调参的小型生产版”，这个判断也很现实。Dify 的知识库文档把 retrieval-ready 的知识维护、metadata 过滤、index method、retrieval strategy 和 retrieval validation 作为日常配置项；它的官方博客则非常明确地强调：只靠向量检索不足以支撑生产 RAG，Hybrid Search 用来补足向量检索在专有名词、短语、ID、低频词上的短板，而 rerank 负责在多种召回结果之间统一比较和排序。对当前 MOCA 来说，这比一开始就上大规模外部搜索集群更符合投入产出比。citeturn4view6turn6view0

你从 Haystack 借来的，是把 pipeline 的“边界感”学过来，这也是对的。Haystack 文档明确把 Routers、Converters、Preprocessors、Rankers、Retrievers 等当作独立组件；`FileTypeRouter` 用来按 MIME type 路由不同文件进入不同预处理链路，`DocumentCleaner` 负责 Unicode normalization、空白清洗、页眉页脚删除等，`DocumentSplitter` 负责 split length / overlap / source_id / page_number 等与 chunk 稳定性直接相关的事项，而 ranker 则被设计成 query pipeline 中位于 retriever 之后的独立模块。你现在把 ingestion 从单一 `IngestionService` 中拆出来，是非常值得继续坚持的。citeturn11view0turn11view1turn12view0turn12view4

## 你现在架构里还需要补强的地方

最重要的一个补强点，是把“规范性契约”和“实现型流水线”分得更清楚。你现在的 spec 已经写得很全面，但如果它要长期演进，建议把内容再硬拆成两类：一类是永远有效的 contract，比如 `EvidenceRefV1`、`EvidenceKey`、`DocumentBlock`、`PolicyChunk`、`SearchRequest`、`SearchHit`、`VerificationResult` 这些领域对象及最小字段集合；另一类是当前实现偏好的 pipeline 策略，比如现在先用 pgvector HNSW、PostgreSQL full-text、pg_trgm、RRF、某个 tokenizer、某个 OCR backend。前者应尽量稳定，后者应允许替换。否则将来你从 PostgreSQL hybrid 升级到 Vespa / OpenSearch，或者从一种 OCR 栈切到另一种 OCR 栈时，容易把 contract 和 implementation 一起拖着重构。这个建议与 Onyx / Haystack 的组件化经验是一致的，也与 MOCA 自己“contract-spec 才是 normative source”的设定相吻合。fileciteturn0file0 citeturn9view0turn11view0turn4view7

第二个补强点，是把 `DocumentBlock` 真的当作“一等数据模型”，而不是暂存结果。你在 spec 里已经给了这个层，但下一步要避免两种常见问题：其一，parser 只吐最终纯文本 chunk，不落 block，导致 page/bbox/表格单元格在后续版本中不可追溯；其二，block 落了，但 chunk 没保存 `source_block_ids`，导致回答端无法把 claim 映射回原始证据。这一点并不是细节优化，而是强 citation、视觉高亮、OCR 低置信度降权、表格行列定位、冲突证据人工复审的前提。RAGFlow deepdoc、Docling、MinerU、PaddleOCR 这些工具之所以有价值，都是因为它们保留了足够丰富的中间结构，而不是只输出一大段 Markdown。citeturn22view0turn16view0turn17view0turn17view1turn17view3turn17view5

第三个补强点，是把“citation membership”和“semantic support”彻底分开，不要在命名或流程上混用。你的 spec 已经明确指出 membership validation 不等于 semantic support，这个判断非常重要，而且有研究支持：RAGTruth 把 RAG 幻觉定义成对检索内容的 unsupported 或 contradictory 生成；SURE-RAG 明确指出 retrieval is not verification，passage topicality 不等于足够支撑答案；RT4CHART 则进一步把答案拆成可验证 claim，并把每个 claim 标成 entailed、contradicted 或 baseless。对客服政策问答来说，这意味着“引用存在”只能证明没有伪造 citation，不能证明回答真的被证据支持。你应该把 verifier 设计成至少两层：第一层做 membership / hash / ACL / staleness 检查，第二层做 claim-evidence 级别的 support/refute/insufficient 判断。fileciteturn0file0 citeturn19academia1turn18academia1turn19academia2

第四个补强点，是把 freshness 和 authority 从 metadata 变成 ranking feature。你已经计划了 `effective_date`、`authority_level`、`supersedes_doc_id`，但如果这些只在后置过滤里使用，模型仍然可能在上下文里同时看到新旧政策并“自行裁决”。更稳妥的做法是：在召回时就先用 `effective_date` 和 ACL 过滤掉显然无效或无权限的候选；在 fusion / rerank 时再对 authority 和 supersedes 关系做加权或排序偏置；最后在 `ContextBuilder` 中对剩余冲突显式打标，而不是让生成阶段静默处理。这样处理与 spec 中“冲突证据要显式标记、过期证据要显式降权”的目标一致。fileciteturn0file0

## Postgres 路线该如何更稳地落地

你现在坚持 Postgres 作为事实源、并把 pgvector + PostgreSQL full-text + pg_trgm 组合成小型检索后端，这个路线是合理的，而且在工程上非常有利于个人项目做出“生产形态的小型版”。`pgvector` 官方 README 明确支持 exact nearest neighbor 与 approximate nearest neighbor 两种模式；近似索引支持 HNSW 与 IVFFlat，其中 HNSW 的速度/召回权衡通常优于 IVFFlat，但会消耗更多内存，且可以按 `m`、`ef_construction`、`hnsw.ef_search` 调参。它也明确给出 cosine similarity 的用法，即 `1 - cosine distance`。这意味着你把 dense retrieval 收敛在 PostgreSQL 里，技术上是完全可行的。citeturn13view3turn4view10turn4view11

对 sparse retrieval，你在术语上最好继续保持克制：把它称为 PostgreSQL full-text sparse retrieval 或 BM25-like，而不要说成“Postgres 原生 BM25”。PostgreSQL 官方文档描述的是 `tsvector` / `tsquery`、GIN 索引、`plainto_tsquery`、`phraseto_tsquery`、`websearch_to_tsquery` 以及 `ts_rank` / `ts_rank_cd` 排名函数；`ts_rank_cd` 考虑了命中词的邻近性和覆盖密度，但它不是以全局 IDF 为基础的标准 BM25。你的 spec 在这点上已经很准确了，建议保持这个表述。fileciteturn0file0 citeturn14view0turn14view1turn13view1turn14view3

至于 `pg_trgm`，它非常适合做你所说的“兜底层”：短 query、规则编号、订单片段、金额、SKU、拼写不规范、分词漏切等。PostgreSQL 官方文档说明 `%` 运算符依赖相似度阈值，`pg_trgm` 支持 GIN / GiST 索引，并可用于 similarity、`LIKE` / `ILIKE`、正则等快速相似搜索。对于中文客服检索，这一层尤其重要，因为很多实际问题并不是规范短语，而是混合着编号、简称、错别字、口语表达。citeturn13view2

你真正要小心的，不是这三种检索能不能做出来，而是**双重一致性**问题。第一，是数据一致性：`content`、`search_text`、`embedding_text` 不能混为一谈。你的 spec 已经提出三者分离，这是正确的，因为回答、关键词检索和向量语义增强服务的是三个不同目标。第二，是索引一致性：一旦你引入独立的 indexing job，就必须记住“文档写入成功 ≠ 三路索引都 ready”。这意味着你应当给 `PolicyChunk` 或独立索引任务表添加更明确的状态机，比如 `parsed -> chunked -> embedded -> indexed_dense -> indexed_sparse -> indexed_fuzzy -> ready`，而不是只有一个笼统的 `index_status`。Onyx 之所以要单独强调后台 worker 和同步作业，本质上就是在解决这种一致性和重试问题。fileciteturn0file0 citeturn9view0

关于融合策略，你选择 RRF 是稳妥的。虽然我没有找到原始 RRF 论文的易检索官方页面，但当前 Dify 对 hybrid + rerank 的论述、以及近期多篇 hybrid RAG 研究都把 rank-based fusion 视为实用做法，原因也很直接：dense、full-text、trigram 三类分数不在同一尺度上，强行加权求和需要繁琐的归一化和大量离线调参，而 rank-based fusion 更易解释、也更稳。你的 spec 里先用 RRF，再把 reranker 设计成可插拔层，这个顺序是对的。fileciteturn0file0 citeturn6view0turn20academia1turn20academia2

## OCR 与解析后端如何选

如果你不打算直接依赖 deepdoc，我建议把 parser/OCR backend 设计成可插拔接口，然后优先做一个“双后端”策略，而不是一开始就押宝单一方案。原因是各家工具的优势不一样。Docling 更像一个通用文档处理框架：支持 PDF、DOCX、PPTX、XLSX、HTML、图片等多种格式，强调 advanced PDF understanding、统一文档表示、OCR、chunking 和对下游 RAG 框架的集成；这类工具很适合做你的“规范 parser contract”验证器。citeturn16view0

PaddleOCR / PP-StructureV3 则更适合做高质量 OCR 和结构化解析能力底座。PaddleOCR 官方仓库明确强调它能把 PDF 与图像转成 LLM-ready 的 Markdown / JSON，PP-StructureV3 提供更细粒度的坐标信息，包括 table cell coordinates 与 text coordinates；同时它支持 100+ 语言，对中英混合客服文档显然更有现实价值。如果你需要页级定位、表格单元格坐标和多语言 OCR，这条路线非常值得认真评估。citeturn17view3turn17view4turn17view5

MinerU 则更接近你当前 spec 想要的“RAG 友好中间产物”：它强调把 PDF、DOCX、PPTX、XLSX、图片和网页转成 LLM-ready Markdown / JSON，支持 scanned docs、多栏布局、cross-page table merging、automatic header/footer removal、human reading order，以及 layout/span visualization。对一个以 citation 和 block 追溯为核心诉求的系统来说，这类“可视化确认输出质量”的能力非常有用，因为它能让你更快定位 parser 错误到底出在 OCR、阅读顺序还是表格重建。citeturn17view0turn17view1turn17view2

因此，更实际的建议不是“选 DeepDoc 还是选别家”，而是：定义 `ParsedBlock` / `ParsedTable` / `FigureBlock` / `ParserTrace` 的统一 contract，然后至少跑两组基线。第一组用一个偏通用的框架型 parser，比如 Docling。第二组用一个偏 OCR/结构化能力强的 parser，比如 PaddleOCR 或 MinerU。比较指标不要只看人工观感，而要看你真正关心的四类结果：页码与 bbox 是否稳定、表格是否保住结构、低置信度区域能否显式打标、以及经过 chunking 后 citation 是否还能回到原始 block。fileciteturn0file0 citeturn16view0turn17view0turn17view3

## 对 hallucination control 的建议

你的 spec 对 hallucination control 的理解是正确的：它不是生成层的单点技巧，而是从数据、检索、上下文到校验的一整条控制链。这个判断和研究界的发现一致。RAGTruth 显示，RAG 系统仍然会产生与检索内容不一致或未被支持的内容；SURE-RAG 明确指出“retrieval is not verification”；RT4CHART 则表明只做粗粒度的 answer-level 评估不足以发现很多上下文不忠实问题，必须分解成 claim 级别再验证。你在 spec 中把 hallucination control 分成数据层、检索层、Context 层、生成层和后置校验层，这是非常成熟的框架。fileciteturn0file0 citeturn19academia1turn18academia1turn19academia2

但如果要继续往前推，我建议你把“claim object”正式建模，而不是只让 verifier 接收一段自由文本。也就是说，生成器最好输出结构化 material claims，每条 claim 自带 claim_id、claim_text、claim_type、risk_level、cited_evidence_ids。这样 semantic verifier 才能稳定地逐条判断 supported / contradicted / insufficient，同时把 bad claims 回流给 regeneration 或人工复核。否则如果 verifier 只能拿整段回答去判，会很难定位是哪个句子出问题，也很难与 UI 层的高亮、citation 气泡、风险提示联动。这个思路与 RT4CHART、SURE-RAG 的 claim-level / evidence-level 验证方向高度一致。citeturn18academia1turn19academia2

另一个容易被低估的点，是“拒答能力”的产品化。你的 spec 已经有 `no evidence`、`partial evidence`、`strong evidence`，这很好，但建议把它进一步转成用户可感知的策略：在低风险 FAQ 中，`partial evidence` 可以允许回答但要明确不确定性；在高风险政策场景中，`partial evidence` 只能触发澄清、转人工或仅给出“需核实”的流程性建议，而不能给出确定动作结论。这样做的意义，不只是更安全，也能让你之后的 eval 更可操作：你可以单独测 refusal accuracy、unsafe answer rate、high-risk manual-review rate，而不是把一切模糊到“整体正确率”里。fileciteturn0file0 citeturn19academia1turn18academia1

## 我会如何调整你的实施优先级

如果按“最符合现实生产需求”的目标来做，我不会推翻你现在的设计，而是会把优先级重新收紧成三段。

第一段，是把最小但正确的证据链做硬。这里包括：固定 `DocumentBlock` / `PolicyChunk` / `EvidenceRefV1` / `SearchRequest` / `SearchHit` / `ClaimVerificationResult` 这些核心对象；把 parser contract、chunk contract、citation contract 从代码组织上独立出来；完成 `content` / `search_text` / `embedding_text` 三分离；并让权限过滤、`effective_date` 过滤在每一路检索之前生效。做到这里，MOCA 就已经有了“可以长期演进的骨架”。fileciteturn0file0

第二段，是把 PostgreSQL hybrid 版本真正做成“生产形态的小型版”，而不是只把 dense 检索再包一层类。这里包括：`pgvector` HNSW 索引、`tsvector` generated column + GIN 索引、`pg_trgm` GIN 索引、应用层中文 tokenizer、RRF 融合、reranker 接口、ContextBuilder、retrieval trace、以及 minimum eval 套件。换句话说，先把你 spec 里的 Phase RAG-1 和 RAG-3 打通，而不是急着进外部搜索后端。官方文档已经足以支撑这些基础设施能力，且与现有栈兼容。fileciteturn0file0 citeturn13view3turn14view1turn13view2turn14view3

第三段，才是引入更重的解析能力和更强的验证能力。也就是：替换或并行接入一到两种 parser/OCR backend；为 PDF/扫描件/表格建立 golden set；再把 semantic support verifier 用到高风险政策与 troubleshooting 场景中。如果未来 chunk 规模、延迟需求或 ranking complexity 明显超过 PostgreSQL hybrid 的舒适区，再加第二检索后端，比如 Vespa 或 OpenSearch，并通过 `SearchBackend` 做 shadow test 或 A/B 切流。这个顺序与你在说明里提到的“Vespa 不是二选一，而是未来可替换 backend”完全一致，我认为这是最稳的路径。fileciteturn0file0 fileciteturn0file1

综合来看，我的建议不是让你大改方向，而是把你已经做对的部分再“制度化”一点：把借鉴来的思想，固化成更少但更硬的 contract；把 OCR / layout / table / page-bbox 视为 citation 的前置条件；把 PostgreSQL hybrid 做扎实，而不是急着扩大战线；把 verifier 从“引用存在检查”升级到“claim 是否真的被证据支持”的两层体系。按这个路线推进，MOCA 会更像一个真正的生产级客服知识系统，而不是“加了几层工程包装的 demo RAG”。fileciteturn0file0 citeturn22view0turn9view0turn6view0turn11view0turn19academia1turn18academia1turn19academia2
# 变更申请：M04 稠密检索腿修复与稠密候选下界（FR-RAG-009）

- **日期**：2026-10-23
- **申请人**：线三 D 标定会话（端到端方案线三）
- **背景**：线三 D 用真实分数复刻默认路径基线时，合成集与 ND-P0-03 记录系统性对不上。探针定位到 `_LlamaDense.search`：它经 `index.as_retriever(similarity_top_k, node_ids=...)` 构造检索器，在 llama-index-core 0.11.23 下抛 TypeError（node_ids 重复传参），异常被 RetrieverError 降级语义吞掉。也就是说，默认 LlamaIndex 路径的稠密通道自集成以来从未返回过命中，检索一直只有 BM25 一条腿；既有测试的问题都词面友好，BM25 单腿即可通过，故未暴露。
- **原契约/现状**：
  - 稠密腿失效期间测得的证据包括：L2 双路径对比（evidence/llama-index-l2/backend-comparison.md）、L4 默认路径实测（evidence/golden-set-eval/default-path-eval.md）、ND-P0-03 live 评测（evidence/golden-set-eval/live-path-eval.md）。三份证据均已加更正节并按修复后口径复测或标注失效。
  - 生产装配的稠密分数下界为 −1.0（`_NO_DENSE_CUTOFF`），即不过滤；稠密一旦恢复，零相似与负相似的块也会进入融合。
- **拟变更内容**（本切片）：
  - `_LlamaDense.search` 改走直接构造 `VectorIndexRetriever(index, similarity_top_k, node_ids)`，绕开 `as_retriever` 的重复传参；异常降级语义不变（真故障仍返回空并记错）。
  - 稠密候选下界由 −1.0 改为 0.0（bootstrap 常量改名 `_DENSE_CUTOFF`；两个受控脚手架 `default_path_eval`、`backend_compare` 同步）：仅正余弦相似度进入融合。0.0 是「有信号才入选」的定义性下界，不是对相关性的调参；调参阈值仍属 ADR-014 门禁与 DR-010，本切片不冻结。
  - 新增 FR-RAG-009 回归测试（受控向量、问题与目标块零词面重叠）：稠密腿端到端可达、稠密搜索返回带分数命中、零相似块在 0.0 下界下不入选。此类「语义命中、词面不命中」用例是此前测试集的盲区。
  - U2 刷新测试的证据断言由精确列表改为成员断言并注明原因：稠密恢复后旧块可经融合一并返回，该测试的要件是新文档免重启可见，不是证据构成。
  - 锁定测试按各自文件头注的规程同步复测值：NFR-QUAL 默认路径锁（合成 94 / 120、企业 67 / 120，均见证据更正节）；L2 对比锁（差异 98 例、LlamaIndex 失败 26 例、泄漏 1 例）与对比报告重新生成，原「行为等价」结论与 Owner 当时的确认一并标注失效，替代结论写在报告 §5。
- **影响模块**：M04（llama_index_retriever、bootstrap、两处评测脚手架、三份证据、锁定测试）；其余模块行为不变。
- **兼容方案**：native 路径不经本代码，不受影响。LlamaIndex 路径的证据构成会变化（稠密命中进入融合），这是修复目的本身；相关性门禁（ADR-014）默认仍关闭，拒答形态与修复前同源（无下限）。
- **测试 ID**：`test_FR_RAG_009_dense_leg_returns_semantic_only_hit`、`test_FR_RAG_009_dense_search_returns_scored_hits`、`test_FR_RAG_009_zero_similarity_is_not_a_dense_candidate`；同步更新 `test_FR_RAG_007_*`（L2 对比三项与 U2 刷新一项）与 `test_NFR_QUAL_*`（两项，合成集一项改名 measured）。
- **是否触发 ADR**：否。修复使实现回到既定混合检索设计；0.0 下界是定义性修正而非阈值决策，ADR-014 已覆盖相关性门禁的决策面。本记录兼作三份证据更正的总登记。
- **审核结果**：随线三 B0 切片提交，待 Owner 随 PR 审核。

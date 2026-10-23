# 变更申请：M04 默认 LlamaIndex 路径补接 rerank

- **日期**：2026-10-22
- **申请人**：ND-P0-03 实施会话（M04 检索全链验证）
- **背景**：ND-P0-03 要求验证真实 dense + BM25 + RRF + bge 全链。复核发现默认问答路径自 LlamaIndex 切换后未接重排：`LlamaIndexRetriever` 内部构造 `RetrievalService` 时未传 reranker，启动装配的 `PIVOT_RERANK` 只接到原生检索服务。问答编排中的 rerank 仅为阶段名，不是实际重排。SPEC FR-RAG-001 的默认链路含 bge 重排，此为切换遗漏，不是新需求。
- **原契约/现状**：
  - `Reranker` 端口与 `HttpBgeReranker` 已冻结并在原生服务接线；
  - `LlamaIndexRetriever` 只做 dense + BM25 + RRF，`PIVOT_RERANK` 对问答路径无效；
  - 重排失败回退融合排序的语义已在 `RetrievalService` 实现。
- **拟变更内容**（本切片）：
  - `LlamaIndexRetriever` 增加可选 reranker 参数并传给内部 `RetrievalService`；未注入时行为与现状完全一致；
  - 启动装配把同一套 `PIVOT_RERANK` 配置（none / overlap / bm25 / bge）同时接到默认问答路径，与原生服务共用同一无状态 reranker 实例；
  - 评测装配 `default_path_eval` 增加可选的 embed_model / vector_size / reranker 注入点，受控基线默认不变；新增 opt-in live 运行器 `ops/run_live_path_eval.py`，密钥经连接器代理注入，不落仓库；
  - **不** 新增依赖；**不** 冻结任何 TBD-P0（阈值、top-k、超时仍注入）；**不** 把 GATE-P0-002 标 verified；**不** 改变授权复核与证据释放顺序（重排只改融合候选的排序，释放前仍逐条实时授权）。
- **影响模块**：M04（llama_index_retriever、评测装配、单元与 pipeline 测试）；M11（bootstrap 接线、运行时接线测试）。
- **兼容方案**：`PIVOT_RERANK=none`（默认）时问答路径行为不变；既有受控评测数字与测试不需改动。
- **测试 ID**：`test_FR_RAG_001_llama_reranker_reorders_fused_evidence`、`test_FR_RAG_004_llama_reranker_failure_falls_back_to_fused`、`test_FR_RAG_004_provider_failure_degrades_safely`、`test_FR_RAG_001_llama_runtime_bge_rerank_wires`、`test_FR_RAG_001_live_hybrid_uses_both_routes`（opt-in，无密钥跳过）。
- **是否触发 ADR**：否（恢复 SPEC 既定链路，不改变状态机、权限、引用/删除语义，不冻结 TBD-P0）。
- **审核结果**：随 ND-P0-03 切片提交，待 Owner 随 PR 审核。

# 变更申请：M04 HTTP Embedding 与 bge-reranker 适配器

- **日期**：2026-09-09
- **申请人**：Wave 3 主线会话（M04 检索供应商适配 + M11 composition root 可选接线）
- **背景**：dense 已消费 Qdrant，但 query embedder 仍为 `HashingQueryEmbedder`；`PIVOT_RERANK` 仅 `none|overlap|bm25`。SPEC FR-RAG-001 默认链路含 Embedding 与 `bge-reranker-v2-m3`。禁止在代码中写死供应商 URL、模型名、维数、超时或 rerank 阈值；单测必须 Fake/Stub HTTP，不得提交密钥；不得把 Fake HTTP 标成 `GATE-P0-002` verified。
- **原契约/现状**：
  - `QueryEmbedder` / `Reranker` 端口已冻结；runtime dense 用哈希 embedder；rerank 非 bge；
  - M07 ingest 仍 `FakeEmbedding`，无 ingest→Qdrant；
  - 维数、距离、top-50、rerank 超时/阈值仍为 `TBD-P0`。
- **拟变更内容**（本切片）：
  - M04 增加注入 endpoint/model/api_key/timeout 的 `HttpQueryEmbedder` 与 `HttpBgeReranker`；请求走注入的 JSON HTTP 客户端（OpenAI embeddings / rerank `results[].index`+score 形状）；缺字段或 HTTP 失败闭环为 `RetrieverError`；异常与日志不回显 api_key；
  - 适配器不写死供应商域名、模型名、1024 维、top-50、阈值；`limit`/k/维数只来自调用方或注入；
  - `RetrievalService`：rerank 抛 `RetrieverError` 时记录 `rerank_failed` 并回退 RRF 顺序（不生成无证据答案）；
  - M11：`PIVOT_EMBEDDING=hash|http`（默认 hash，兼容既有 Qdrant 测试）；`http` 时必须同时注入 `PIVOT_EMBEDDING_ENDPOINT`/`MODEL`/`API_KEY`，且要求 `PIVOT_VECTOR_STORE=qdrant`；`PIVOT_RERANK=bge` 时必须注入 rerank endpoint/model/api_key；可注入 `json_http_client`；timeout 可选注入，不填默认秒数；
  - **不** 新增 pyproject 依赖（stdlib `urllib`）；**不** 调用真实供应商；**不** 做 ingest→Qdrant / Celery；**不** 冻结 TBD-P0；**不** 把 `GATE-P0-002` 标 verified。
- **影响模块**：M04（providers、RetrievalService、单元测试）；M11（settings/bootstrap、pipeline 测试、证据）；M07（仍 Fake Embedding，本切片不接线 ingest）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：默认 `PIVOT_EMBEDDING=hash` 且 `PIVOT_RERANK=none` 时 runtime 行为不变；既有 Qdrant/BM25 测试保持哈希 embedder 与 overlap/bm25 rerank。
- **测试 ID**：`test_FR_RAG_001_http_embedder_posts_injected_model_and_input`、`test_FR_RAG_001_http_embedder_uses_injected_dimension`、`test_FR_RAG_001_http_embedder_does_not_hardcode_vendor`、`test_FR_RAG_001_http_embedder_failure_is_provider_error`、`test_FR_RAG_001_http_embedder_does_not_leak_api_key`、`test_FR_RAG_001_bge_rerank_reorders_by_provider_score`、`test_FR_RAG_001_bge_rerank_uses_injected_limit`、`test_FR_RAG_001_bge_rerank_does_not_freeze_threshold`、`test_FR_RAG_004_bge_rerank_failure_falls_back_to_fused`、`test_NFR_OBS_runtime_http_embedding_requires_endpoint_model_key`、`test_NFR_OBS_runtime_http_embedding_requires_qdrant`、`test_NFR_OBS_runtime_qdrant_http_embedder_wires`、`test_FR_RAG_001_runtime_http_embedder_retrieve`、`test_NFR_OBS_runtime_bge_rerank_requires_endpoint_model_key`、`test_FR_RAG_001_runtime_bge_rerank_reorders`、`test_GATE_P0_002_not_verified_by_http_embedding_bge`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义；不冻结 TBD-P0 模型/维数/超时/阈值；不把 Fake HTTP 标成生产 Embedding/rerank）。
- **审核结果**：2026-09-09 Wave 3 主线会话 **批准**。

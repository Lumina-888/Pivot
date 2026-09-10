# 变更申请：worker 装配 Qdrant IndexPublisher

- **日期**：2026-09-10
- **申请人**：Wave 3 主线会话（M07 worker 进程装配 + M11 Compose 注入）
- **工单**：ND-W3-01
- **背景**：HTTP ingest 在 `PIVOT_VECTOR_STORE=qdrant` 时可 `upsert`；Compose worker 只接了 PG/MinIO，发布仍停在进程内 `IndexPublisher`，API 检索看不见 worker 产物。SPEC §6.2 / `FR-DOC-006` / `FR-RAG-001` 要求索引发布与检索共用同一向量端口。不得把 Fake Qdrant / Hashing embedder 标成 `GATE-P0-002` / `GATE-P0-003` verified，不得冻结维数/距离。
- **原契约/现状**：
  - `assemble_ingest_runtime` 只装配 PG 事实 + MinIO 对象；`DocumentIngestRunner` 使用默认内存 `IndexPublisher` 与 `FakeEmbedding`；
  - Compose worker 未注入 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*`；
  - HTTP `assemble_runtime` 在 `PIVOT_VECTOR_STORE=qdrant` 时已接线 `IndexPublisher` + 同一 query embedder。
- **拟变更内容**（本切片）：
  - M07：`assemble_ingest_runtime` 在 `PIVOT_VECTOR_STORE=qdrant` 时装配 `QdrantVectorStore` + `IndexPublisher(store=...)` + 注入维数的 `HashingQueryEmbedder`（与 API 同一向量空间）；缺 endpoint/collection/vector_size 失败闭环；CI 注入 Fake Qdrant client，不启动容器；
  - `vector_store=memory` 仍允许（进程内 IndexPublisher）；不接 HTTP Embedding（属 ND-STG-01）；
  - M11：Compose `worker` 注入 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*`（`${}`，不写死 URL/维数/距离）；`ops/compose.env.example` 给可选占位（fixture，不是冻结 TBD-P0）；
  - **不** 改 HTTP 缺省 `PIVOT_INGEST=sync`；**不** 在 CI `docker compose up` / `docker build`；**不** 把 Compose api 必选接到 Qdrant（属 ND-W3-12）；**不** 冻结维数/距离/模型；**不** 把 `GATE-P0-002` / `GATE-P0-003` 标 verified。
- **影响模块**：M07（worker 装配、单元测试）；M11（Compose worker 环境、pipeline 测试、证据、intent）；M03（只消费既有 VectorStore 端口）；M04（只消费已写入的 payload / 同一 Hashing embedder）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：默认 `PIVOT_VECTOR_STORE=memory` 行为不变；缺 Qdrant 变量且选中 qdrant 时失败闭环，不回退静默 memory。
- **测试 ID**：`test_FR_DOC_006_worker_qdrant_publish_requires_endpoint`、`test_FR_DOC_006_worker_qdrant_publish_requires_collection`、`test_FR_DOC_006_worker_qdrant_publish_requires_vector_size`、`test_FR_DOC_006_worker_qdrant_publish_rejects_unsupported_store`、`test_FR_DOC_006_worker_qdrant_publish_wires_index_publisher`、`test_FR_DOC_006_worker_qdrant_publish_search_roundtrip`、`test_NFR_OBS_compose_worker_injects_qdrant`、`test_GATE_P0_002_not_verified_by_worker_qdrant`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不冻结维数/距离；不把 Fake Qdrant 标成生产索引发布）。
- **审核结果**：2026-09-10 Wave 3 主线会话 **批准**。

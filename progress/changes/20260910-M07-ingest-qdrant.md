# 变更申请：M07 ingest 索引代次写入 VectorStore（Qdrant 端口）

- **日期**：2026-09-10
- **申请人**：Wave 3 主线会话（M07 IndexPublisher 写入 VectorStore + M11 composition root 接线）
- **背景**：dense 检索已消费 `QdrantVectorStore`，但 ingest/`IndexPublisher` 只在进程内缓冲向量，不调用 `VectorStore.upsert`。HANDOFF / PROGRESS 下一刀是 ingest→Qdrant。禁止写死维数/距离/供应商 URL；CI 必须 Fake/内存 client；不得把 Fake upsert 标成 `GATE-P0-003` verified。
- **原契约/现状**：
  - M07 `IndexPublisher.publish` 只把代次标为 `published`，不写存储端口；
  - `IngestWorker` Embedding 为 `FakeEmbedding`；payload 仅 `version_id + chunk_id + text_hash`；
  - M04 从 Qdrant payload 水合检索需要 `document_id`/`text`/`ready`/`current`/`allowed`；
  - 维数、距离、k、Embedding 模型仍为 `TBD-P0`；无 Celery、无 Compose worker。
- **拟变更内容**（本切片）：
  - M07 `IndexPublisher` 可注入 `VectorStore`；`publish` 在标 `published` 前对注入端口 `upsert`；payload 含 `version_id + chunk_id` 以及检索水合字段（`document_id`/`text`/`title`/`space`/`ready`/`current`/`allowed`/`index_generation`/`embedding_model_version`/`retrieval_config_version`）；缺 `document_id` 失败闭环；upsert 失败不 `published`、不回调 `IngestSink.on_publish`；
  - `IngestRequest` 可携带 `document_id` 等元数据；`IngestWorker` 把 chunk 文本与元数据写入 payload；Embedding 端口改为可注入（duck-type `embed`），默认仍 `FakeEmbedding`；
  - M11：`PIVOT_VECTOR_STORE=qdrant` 时 `IndexPublisher(store=qdrant)`，ingest embedding 复用 query embedder（同一向量空间）；CI 内存 Qdrant client；**不** 在 HTTP 上传路径自动跑 Worker；**不** 接 Celery/Compose worker；**不** 调用 live 供应商；**不** 冻结 TBD-P0；**不** 把 `GATE-P0-002/003` 标 verified。
- **影响模块**：M07（IndexPublisher / IngestWorker / 单元测试）；M11（bootstrap、pipeline 测试、证据）；M03（只消费既有 VectorStore）；M04（只消费已写入的 payload）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：未注入 VectorStore 时 `IndexPublisher` 行为不变；既有 7 项 M07 测试保持 Fake Embedding / 内存代次；默认 `PIVOT_VECTOR_STORE=memory` 不接线 ingest。
- **测试 ID**：`test_FR_DOC_006_index_publisher_upserts_injected_vector_store`、`test_FR_DOC_006_index_publisher_requires_document_id_for_vector_store`、`test_FR_DOC_006_vector_store_failure_does_not_publish`、`test_FR_DOC_006_ingest_writes_retrieval_payload`、`test_FR_DOC_005_duplicate_message_does_not_duplicate_vector_upsert`、`test_FR_DOC_006_ingest_does_not_freeze_dimension`、`test_NFR_OBS_runtime_qdrant_wires_index_publisher`、`test_FR_DOC_006_runtime_ingest_qdrant_search_roundtrip`、`test_FR_RAG_006_runtime_ingest_qdrant_index_generation`、`test_GATE_P0_003_not_verified_by_ingest_qdrant`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义；不冻结 TBD-P0 维数/距离/模型；不把 Fake upsert 标成生产索引发布）。
- **审核结果**：2026-09-10 Wave 3 主线会话 **批准**。

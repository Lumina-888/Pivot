# 变更申请：PostgreSQL 文档事实源（Document/Version/Chunk/Task）

- **日期**：2026-09-10
- **申请人**：Wave 3 主线会话（M03 持久化客户端 + M02 端口消费 + M11 composition root）
- **背景**：`PIVOT_STORAGE=postgres` 已装配 `SqlAlchemyUserDirectory`，但 `DocumentService` 仍用内存 Document/Version/Chunk/Task。Compose worker / Celery 跨进程看不到上传。SPEC §2.1 规定文档事实在 PostgreSQL。不得把 sqlite 标成生产事实源，不得冻结 TBD-P0。
- **原契约/现状**：
  - M03 已有 `documents` / `document_versions` / `chunks` / `celery_tasks` 模型与迁移；
  - M02 `DocumentStore`/`VersionStore`/`ChunkStore`/`TaskStore` 端口已冻结；
  - composition root 在 postgres 模式下仍 `MemoryDocuments()`。
- **拟变更内容**（本切片）：
  - M03 `SqlAlchemyDocumentStore` / `VersionStore` / `ChunkStore` / `TaskStore`：按现有模型读写 M02 端口字段；`created_by` 依赖已有 User 行；tags 以 JSON 文本存放；
  - 本切片 **不** 新增 `idempotency_key`/`error_code` 列（非 SPEC §2.2 DocumentVersion 字段；内容幂等仍走 `content_sha256`）；
  - M02：`publish` 在标记 `chunk.published` 后写回 ChunkStore；`ChunkStore.add` 按 id upsert，避免内存与 SQL 语义分叉；
  - M11：`PIVOT_STORAGE=postgres` 时文档四端口与用户目录共用同一 session factory；缺 URL 仍失败闭环；
  - **不** 引入 Celery；**不** 把 HTTP 上传改成入队；**不** 把 `GATE-P0-003` 标 verified。
- **影响模块**：M03（SQL 适配、db 测试）；M02（publish 写回 chunk、内存 add upsert）；M11（bootstrap、pipeline 测试、证据）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：默认 `PIVOT_STORAGE=memory`；既有文档单元测试仍走内存 fake；CI sqlite 覆盖跨装配存活。
- **测试 ID**：`test_M03_sqlalchemy_document_store_persists_spec_fields`、`test_M03_sqlalchemy_version_store_roundtrip_and_sha`、`test_M03_sqlalchemy_chunk_and_task_roundtrip`、`test_NFR_OBS_runtime_postgres_wires_document_facts`、`test_FR_DOC_001_runtime_postgres_upload_survives_new_assembly`、`test_GATE_P0_003_not_verified_by_postgres_document_facts`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不把 sqlite 标成生产事实源）。
- **审核结果**：2026-09-10 Wave 3 主线会话 **批准**。

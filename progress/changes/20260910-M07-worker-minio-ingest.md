# 变更申请：worker 装配共享 MinIO/PG ingest runner

- **日期**：2026-09-10
- **申请人**：Wave 3 主线会话（M07 worker 进程装配 + M11 Compose 注入）
- **背景**：Compose worker 已是注入 Redis broker 的 Celery，只听 parse 队列；任务到达仍走 `_unassembled_runner`，缺共享 ObjectStore 会失败闭环。SPEC §2.1 规定文档事实在 PostgreSQL、原文在 MinIO；跨进程不得把内存对象当事实。不得把 Fake MinIO / sqlite / Compose fixture 标成 `GATE-P0-003` / `GATE-P0-008` verified，不得冻结 TBD-P0。
- **原契约/现状**：
  - `python -m pivot_worker` 只启动 `/healthz` + Celery，runner 未装配；
  - Compose worker 只注入队列名、concurrency 与 `PIVOT_CELERY_BROKER`；
  - HTTP `assemble_runtime` 已能接 PG 文档事实与 MinIO 对象；缺省仍为进程内 ingest。
- **拟变更内容**（本切片）：
  - M07：`assemble_ingest_runtime` 为 worker 装配 `DocumentIngestRunner` + `DocumentService`（`PIVOT_STORAGE=postgres` + 共享 `PIVOT_OBJECT_STORE=minio`）；`storage=memory` 或 `object_store=memory` 失败闭环；缺 `PIVOT_DATABASE_URL` / MinIO endpoint·bucket·密钥失败闭环；CI 用 sqlite URL + 注入 Fake MinIO client，不启动容器；
  - `python -m pivot_worker` 在启动 Celery 前装配 runner，不再使用 `_unassembled_runner`；
  - M11：Compose `worker` 注入 `PIVOT_STORAGE` / `PIVOT_DATABASE_URL` / `PIVOT_OBJECT_STORE` / MinIO 变量（`${}`，不写死 URL）；`ops/compose.env.example` 给 fixture 占位（不是冻结 TBD-P0）；
  - **不** 改 HTTP 缺省 `PIVOT_INGEST=sync`；**不** 在 CI `docker compose up` / `docker build`；**不** 把 worker 接到 Qdrant 作为本切片必选项；**不** 引入 PyMuPDF；**不** 冻结 concurrency/broker/endpoint；**不** 把 `GATE-P0-003` / `GATE-P0-008` 标 verified。
- **影响模块**：M07（worker 装配、进程入口、单元测试）；M11（Compose worker 环境、pipeline 测试、证据、intent）；M02（只消费既有 `prepare_ingest` / ObjectStore.get）；M03（只消费既有 PG/MinIO 端口）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：HTTP 缺省仍进程内 ingest；未开 `app` profile 时依赖 fixture 不变；缺共享存储变量失败闭环，不回退 memory。
- **测试 ID**：`test_FR_DOC_006_worker_ingest_rejects_memory_storage`、`test_FR_DOC_006_worker_ingest_rejects_memory_object_store`、`test_FR_DOC_006_worker_ingest_requires_database_url`、`test_FR_DOC_006_worker_ingest_requires_minio_endpoint`、`test_FR_DOC_006_worker_ingest_reads_shared_minio_object`、`test_FR_DOC_006_worker_ingest_does_not_see_memory_objects`、`test_NFR_OBS_worker_process_assembles_ingest_runner`、`test_NFR_OBS_compose_worker_injects_shared_storage_and_minio`、`test_GATE_P0_003_not_verified_by_worker_minio_ingest`、`test_GATE_P0_008_not_verified_by_compose_worker`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不冻结 endpoint/concurrency；不把 Fake MinIO / sqlite / Compose fixture 标成生产跨进程存储）。
- **审核结果**：2026-09-10 Wave 3 主线会话 **批准**。

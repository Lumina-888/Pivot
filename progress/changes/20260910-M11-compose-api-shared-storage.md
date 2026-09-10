# 变更申请：Compose api 注入共享 PG/MinIO

- **日期**：2026-09-10
- **申请人**：Wave 3 主线会话（M11 Compose 装配）
- **背景**：Compose worker 已注入 `PIVOT_STORAGE` / `PIVOT_DATABASE_URL` / `PIVOT_OBJECT_STORE` / MinIO 变量并装配 ingest runner。Compose api 仍 `PIVOT_STORAGE:-memory`，未注入 DATABASE_URL/MinIO，profile `app` 下 HTTP 上传与 worker 不能读同一事实/对象。SPEC §2.1 规定文档事实在 PostgreSQL、原文在 MinIO。不得把 Compose fixture / Fake MinIO / sqlite 标成 `GATE-P0-008` verified，不得冻结 TBD-P0。
- **原契约/现状**：
  - Compose `api`：`PIVOT_STORAGE` / `PIVOT_OBJECT_STORE` 缺省 `memory`，无 `PIVOT_DATABASE_URL` 与 MinIO 变量；
  - `ops/compose.env.example` 仍写 `PIVOT_STORAGE=memory`；
  - HTTP `assemble_runtime` 已能接 PG + MinIO；缺省仍进程内 ingest。
- **拟变更内容**（本切片）：
  - Compose `api` 注入与 worker 相同的 `PIVOT_STORAGE` / `PIVOT_DATABASE_URL` / `PIVOT_OBJECT_STORE` / MinIO 变量（`${:?}`，不写死 URL，不静默 `:-memory`）；
  - `ops/compose.env.example` 的 app profile 占位改为 `postgres` + `minio`（fixture，不是冻结 TBD-P0）；
  - pipeline 证明 HTTP composition root 与 worker assembly 可共享同一 Fake MinIO 对象字节与 PG version；
  - **不** 改 HTTP 缺省 `PIVOT_INGEST=sync`；**不** 在 CI `docker compose up` / `docker build`；**不** 把 api 必选接到 Qdrant/Redis；**不** 冻结 endpoint/TTL；**不** 把 `GATE-P0-003` / `GATE-P0-008` 标 verified。
- **影响模块**：M11（Compose api 环境、pipeline 测试、证据、intent）；M02（只消费既有 HTTP 上传 / ObjectStore）；M03（只消费既有 PG/MinIO 端口）；M07（只消费既有 worker assembly）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：未开 `app` profile 时依赖 fixture 不变；进程外 `assemble_runtime` 缺省仍 memory；Compose app 缺共享存储变量失败闭环。
- **测试 ID**：`test_NFR_OBS_compose_api_injects_shared_storage_and_minio`、`test_NFR_OBS_compose_api_does_not_default_storage_to_memory`、`test_FR_DOC_001_http_and_worker_share_minio_object`、`test_GATE_P0_008_not_verified_by_compose_api`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不冻结 endpoint；不把 Compose fixture 标成生产跨进程存储）。
- **审核结果**：2026-09-10 Wave 3 主线会话 **批准**。

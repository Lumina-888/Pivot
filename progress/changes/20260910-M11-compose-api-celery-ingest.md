# 变更申请：Compose api 注入 `PIVOT_INGEST=celery`

- **日期**：2026-09-10
- **申请人**：Wave 3 主线会话（M11 Compose 装配）
- **工单**：ND-W3-02
- **背景**：api 与 worker 已共享 PG/MinIO，Compose worker 已听 parse 队列并装配 ingest runner。Compose api 未注入 `PIVOT_INGEST` / 队列 / concurrency / broker，HTTP 缺省仍请求内 ingest，profile `app` 下 worker 收不到生产路径任务。SPEC §9.1 / `FR-DOC-005` 要求 Celery 解析队列与在线队列隔离并明确 concurrency。CI 不得 `docker compose up` / `docker build`。不得把 fixture / eager Celery 标成 `GATE-P0-003` / `GATE-P0-008` verified，不得冻结 TBD-P0。
- **原契约/现状**：
  - Compose `api` 未注入 `PIVOT_INGEST` / `PIVOT_PARSE_QUEUE` / `PIVOT_ONLINE_QUEUE` / `PIVOT_WORKER_CONCURRENCY` / `PIVOT_CELERY_BROKER`；
  - 根 `Dockerfile` 只安装 `./api[http,postgres,minio,qdrant,redis]`，无 `pivot_worker[celery]`，无法入队；
  - `assemble_runtime` 缺省 `PIVOT_INGEST=sync`；`celery` 时已能 eager 入队（CI memory broker）。
- **拟变更内容**（本切片）：
  - Compose `api` 注入 `PIVOT_INGEST` / 队列名 / concurrency / `PIVOT_CELERY_BROKER`（`${:?}`，不写死 `redis://`，不静默 `:-sync`）；
  - `ops/compose.env.example` 的 app profile 占位 `PIVOT_INGEST=celery`（fixture，不是冻结 TBD-P0）；**不** 注入 `PIVOT_CELERY_EAGER=1`；
  - 根 `Dockerfile` 复制 worker 并安装 `./worker[celery]`，`CMD` 仍为 uvicorn factory，以便 api 进程调用既有 `CeleryIngestSubmitter`；
  - **不** 改进程外 `assemble_runtime` 缺省 `sync`；**不** 在 CI `docker compose up` / `docker build`；**不** 把 api 必选接到 Qdrant/Redis 业务端口（属 ND-W3-12）；**不** 冻结 concurrency/broker；**不** 把 `GATE-P0-003` / `GATE-P0-008` 标 verified。
- **影响模块**：M11（Dockerfile、Compose api 环境、pipeline 测试、证据、intent）；M07（只消费既有 submitter）；M02（只消费既有 HTTP 入队 / 信封 `uploaded`）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：未开 `app` profile 时依赖 fixture 不变；进程外 `assemble_runtime` 缺省仍 sync；Compose app 缺 ingest/队列/broker 变量失败闭环。
- **测试 ID**：`test_NFR_OBS_api_dockerfile_installs_celery_extra`、`test_NFR_OBS_compose_api_injects_celery_ingest_without_hardcoding`、`test_NFR_OBS_compose_api_does_not_default_ingest_to_sync`、`test_FR_DOC_001_http_celery_envelope_stays_uploaded`、`test_GATE_P0_003_not_verified_by_compose_api_celery`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不冻结 concurrency/broker；不把 Compose fixture 标成生产跨进程队列）。
- **审核结果**：2026-09-10 Wave 3 主线会话 **批准**。

# 变更申请：M07 Celery ingest 可见 PostgreSQL version/task

- **日期**：2026-09-10
- **申请人**：Wave 3 主线会话（M07 Celery 任务适配 + M11 composition root 接线）
- **背景**：文档事实（Document/Version/Chunk/Task）已可走 `PIVOT_STORAGE=postgres`。HANDOFF / PROGRESS 下一刀是 Celery 队列：Worker 至少能看见 PG 中的 version/task。对象字节仍需共享 ObjectStore/MinIO。`20260906-M07-worker-dependencies.md` 曾暂缓 Celery extra；本切片只落实 Celery，不引入 PyMuPDF。不得把 eager Celery 标成 `GATE-P0-003` verified，不得冻结 concurrency / broker URL。
- **原契约/现状**：
  - HTTP 上传后进程内 `DocumentIngestRunner`；Compose worker 为 ping，非 Celery；
  - `worker/pyproject.toml` 无 Celery extra；CI `pip install -e ./worker`；
  - Redis QueueStore 不是 Celery broker；CeleryTask 表已存在并可经 `SqlAlchemyTaskStore` 读写。
- **拟变更内容**（本切片）：
  - M07：`worker` optional extra `celery`（`celery>=5.4,<5.6`）；`CeleryIngestSubmitter` 把既有 `DocumentIngestRunner` 注册为 parse 队列任务；parse/online 队列必须隔离；concurrency 与 broker 只注入、不写死；测试用 eager + 注入 `memory://`，不启动 Redis broker；
  - 任务根据 `version_id` 经 DocumentService 读取 version，`prepare_ingest` 把 task 写入 TaskStore（PG 时可跨装配看见）；
  - M11：`PIVOT_INGEST=sync|celery`（缺省 `sync`，既有进程内 ingest 不变）；`celery` 时要求 `PIVOT_PARSE_QUEUE` / `PIVOT_ONLINE_QUEUE` / `PIVOT_WORKER_CONCURRENCY` / `PIVOT_CELERY_BROKER`，可选 `PIVOT_CELERY_EAGER=1`；CI 安装 `worker[celery]`；
  - **不** 改 Compose worker CMD 为 celery worker；**不** 引入 PyMuPDF；**不** 把对象字节标成跨进程共享 MinIO；**不** 冻结 TBD-P0；**不** 把 `GATE-P0-003` 标 verified。
- **影响模块**：M07（Celery extra、任务适配、单元测试）；M11（settings/bootstrap、CI、pipeline 测试、证据）；M02（只消费既有 prepare_ingest）；M03（只消费既有 Task/Version 端口）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：缺省 `PIVOT_INGEST=sync`；未装 celery extra 时不得选 `celery`（失败闭环）；Compose worker 仍为 ping fixture。
- **测试 ID**：`test_FR_DOC_005_celery_requires_isolated_parse_and_online_queues`、`test_FR_DOC_005_celery_requires_broker`、`test_FR_DOC_005_celery_eager_ingest_reaches_ready`、`test_FR_DOC_005_celery_duplicate_message_does_not_reingest`、`test_FR_DOC_005_celery_task_routes_to_parse_queue`、`test_FR_DOC_005_celery_source_has_no_hardcoded_broker`、`test_FR_DOC_005_celery_loads_postgres_version_and_task`、`test_NFR_OBS_runtime_celery_requires_queues_and_broker`、`test_NFR_OBS_runtime_celery_wires_eager_submitter`、`test_FR_DOC_001_http_celery_envelope_stays_uploaded`、`test_FR_DOC_001_http_celery_eager_detail_is_ready`、`test_GATE_P0_003_not_verified_by_celery_ingest`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不冻结 concurrency/broker；不把 eager Celery 标成生产队列）。
- **审核结果**：2026-09-10 Wave 3 主线会话 **批准**。PyMuPDF/python-docx 等解析库仍按 `20260906-M07-worker-dependencies.md` 暂缓。

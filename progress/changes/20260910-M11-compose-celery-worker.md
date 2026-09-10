# 变更申请：Compose worker 以 Celery 消费 Redis broker（parse 队列）

- **日期**：2026-09-10
- **申请人**：Wave 3 主线会话（M11 Compose 装配 + M07 worker 进程入口）
- **背景**：`PIVOT_INGEST=celery` 已能 eager 看见 PG version/task，但 Compose worker 仍是 ping。SPEC §9.1 要求 Celery 解析队列与在线队列隔离并明确 concurrency。CI 不得 `docker compose up` / `docker build`。不得把 fixture 标成 `GATE-P0-008` verified。对象字节仍需共享 ObjectStore；本切片不装配 worker 侧 MinIO ingest runner。
- **原契约/现状**：
  - `Dockerfile.worker` 安装 `./worker`（无 celery extra），`CMD` 为 `python -m pivot_worker` 死循环 ping；
  - Compose worker 只注入队列名与 concurrency；无 `PIVOT_CELERY_BROKER`；
  - 测试明确禁止 Dockerfile/Compose 出现 celery。
- **拟变更内容**（本切片）：
  - `Dockerfile.worker` 安装 `./worker[celery]`，`CMD` 仍为 `python -m pivot_worker`；不写死 broker URL；
  - `WorkerSettings` 要求 `PIVOT_CELERY_BROKER`；`python -m pivot_worker` 在 `/healthz` 之后启动 Celery worker，**只监听 parse 队列**；
  - Compose `worker` 注入 `PIVOT_CELERY_BROKER: ${PIVOT_CELERY_BROKER:?}`，compose.yml 不写死 `redis://`；`ops/compose.env.example` 给 fixture 占位（不是冻结 TBD-P0）；
  - **不** 在 CI 构建或启动容器；**不** 改 HTTP 缺省进程内 ingest；**不** 把 worker 接到共享 MinIO 对象字节；**不** 冻结 concurrency/broker；**不** 把 `GATE-P0-008` 标 verified。
- **影响模块**：M11（Dockerfile.worker、Compose、pipeline 测试、证据、intent）；M07（WorkerSettings、进程入口、Celery worker 启动）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：未开 `app` profile 时依赖 fixture 不变；CI 默认 skip `:8001`；缺 broker 失败闭环。
- **测试 ID**：`test_NFR_OBS_worker_dockerfile_installs_celery_extra`、`test_NFR_OBS_compose_worker_injects_celery_broker_without_hardcoding`、`test_FR_DOC_006_worker_settings_require_celery_broker`、`test_FR_DOC_006_celery_worker_consumes_parse_queue_only`、`test_NFR_OBS_worker_process_starts_celery`、`test_GATE_P0_008_not_verified_by_compose_worker`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义；不冻结 concurrency/broker；不把 Compose fixture 标成生产 Celery）。
- **审核结果**：2026-09-10 Wave 3 主线会话 **批准**。

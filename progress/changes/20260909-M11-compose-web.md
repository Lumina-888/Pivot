# 变更申请：M11 Dockerfile.web 与 Compose web 服务

- **日期**：2026-09-09
- **申请人**：Wave 3 主线会话（M11 运维装配）
- **背景**：Next 已把同源 `/api/v1` rewrite 到注入的 `PIVOT_API_ORIGIN`。Compose 仅有四依赖 + profile `app` 的 `api`。SPEC §9.1 要求 Compose、固定镜像 tag、healthcheck、启动依赖和资源 limits/reservations。CI 不得 `docker compose up` / `docker build`。不得把 fixture 标成 `GATE-P0-008` verified。本切片不做 worker/Celery、不冻结 ECS 4C8G。
- **原契约/现状**：
  - 根目录仅有 API `Dockerfile`；无 web 镜像；
  - Compose 无 `web` 服务；`ops/compose-intent.md` 写明 web 未启用；
  - `tests/integration/pipeline/test_NFR_OBS_compose_deps.py` 与 compose-api 测试禁止 `web`。
- **拟变更内容**（本切片）：
  - 根 `Dockerfile.web`：钉 `node:20.19.0-bookworm-slim`（不是 `latest`），`npm ci` + `next build`，`CMD` 为 `next start --hostname 0.0.0.0 --port 3000`；不拷贝密钥/`.env`；不写死生产 URL；
  - `docker-compose.yml` 增加 `web` 服务：`profiles: [app]`，默认 `docker compose up` 仍只起依赖；镜像 tag `pivot-web:0.1.0`；端口 `127.0.0.1:3000`；healthcheck 探测 `/login`；`depends_on` `api` `service_healthy`；`deploy.resources` limits/reservations（fixture，不写死 ECS 4C8G）；`PIVOT_API_ORIGIN` 只做 `${}` 注入，缺省失败闭环，不把供应商 URL 写进镜像；
  - `ops/compose.env.example` 补充 `PIVOT_API_ORIGIN` 占位并标明不是生产 URL / 不是冻结的 `TBD-P0`；
  - 更新依赖/api 切片测试：禁止列表改为仅 `worker`；
  - **不** 新增 Compose `worker`；**不** 在 CI 构建或启动容器；**不** 改登录/Cookie 语义；**不** 把 `GATE-P0-008` 标 verified。
- **影响模块**：M11（Dockerfile.web、Compose、pipeline 测试、证据、intent/runbook）；M08 只被镜像拷贝既有 Next 工程，不改页面；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：未开 `app` profile 时依赖 fixture 行为不变；CI 默认 skip 对 `:3000` 的探测；`PIVOT_REQUIRE_COMPOSE_WEB=1` 时端口不可达失败闭环。
- **测试 ID**：`test_NFR_OBS_web_dockerfile_pins_node_and_next_start`、`test_NFR_OBS_compose_web_service_is_profiled_with_healthcheck`、`test_NFR_OBS_compose_web_injects_api_origin_without_production_url`、`test_NFR_OBS_compose_does_not_start_worker`、`test_NFR_OBS_ci_does_not_build_or_start_compose_web`、`test_NFR_OBS_compose_web_login_when_running`、`test_GATE_P0_008_not_verified_by_compose_web`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不冻结 ECS 规格/浏览器版本）。
- **审核结果**：2026-09-09 Wave 3 主线会话 **批准**。

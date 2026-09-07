# 变更申请：M11 薄 HTTP 装配仅健康检查

- **日期**：2026-09-07
- **申请人**：M11 集成/质量/运维（Wave 3 依赖 Compose 切片）
- **背景**：SPEC §9.2 要求应用提供 `/healthz` 与 `/readyz`。当前 `api/` 无 FastAPI、无 app factory；`api/pyproject.toml` 由 M03 所有，且 Wave 1 依赖类变更仍暂缓写入。本切片只落地依赖 Compose fixture，不能越权改 `api/`。
- **原契约/现状**：`contract-v0.1` 未定义 `/healthz` `/readyz` 响应体；MODULE_SPEC M11 允许 `docker-compose*.yml`、`ops/**`、`tests/integration/**`，不允许修改 `api/src/pivot/**` 或 `api/pyproject.toml`。
- **拟变更内容**（批准前不得实现）：
  - M03 在 `api/pyproject.toml` 增加 optional extra，例如 `http = ["fastapi", "httpx", "uvicorn"]`，不把 FastAPI 写成默认必装依赖；
  - MODULE_SPEC 增补 M11 可修改 `api/src/pivot/http/**`（仅装配，不实现业务状态机）；
  - 最小表面：`create_app()`、`GET /healthz`（存活，不探依赖）、`GET /readyz`（对 PG/MinIO/Qdrant/Redis 注入探测，缺失则失败闭环）；
  - **不**在该切片挂 `/api/v1` 认证、文档、SSE 或导出路由。
- **影响模块**：M03（pyproject）；M11（薄 HTTP 与集成测试）；M00（若需把健康路径写入契约再另申请）。
- **兼容方案**：无 FastAPI 时现有领域单测与 Fake 链路不变；CI 仍不强制启动 Compose。
- **测试 ID**：后续 `test_NFR_OBS_healthz_*`、`test_NFR_OBS_readyz_*`（尚未编写）。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置）。
- **审核结果**：待 M03/M00 审核。未批准前不得写入 FastAPI 或改 pyproject。

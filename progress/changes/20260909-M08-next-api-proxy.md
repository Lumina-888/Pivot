# 变更申请：Next 反代 `/api/v1`

- **日期**：2026-09-09
- **申请人**：Wave 3 主线会话（M08 next.config + M11 证据）
- **背景**：composition root 已可 `uvicorn pivot.http.main:app --factory` 挂载 `/api/v1`。员工登录页与 API client 仍 `fetch("/api/v1/...")`，但 Next 无 rewrite，本地开发登录 404。MODULE_SPEC 禁止浏览器直连供应商，也禁止写死生产 URL。
- **原契约/现状**：`web/lib/api/client.ts` 的 `API_BASE=/api/v1`；`web/next.config.mjs` 无 `rewrites`。浏览器应继续走同源 `/api/v1`，由 Next 转发到 FastAPI。
- **拟变更内容**：
  - M08 增加 `apiProxyRewrites(origin)`：把 `/api/v1/:path*` 转到注入的 `PIVOT_API_ORIGIN`；缺省则不挂 rewrite（页面仍可开，登录仍 404，失败闭环）；
  - `next.config.mjs` 的 `rewrites()` 读取 `PIVOT_API_ORIGIN`；origin 必须是绝对 `http(s)` 且不含 path/query/凭证；
  - 浏览器 `API_BASE` 保持 `/api/v1`，不把后端 origin 暴露为 `NEXT_PUBLIC_*`；
  - 提供 `web/.env.example` 本地占位（`http://127.0.0.1:8000`），不是生产 URL；
  - **不**启动 Next/uvicorn/Compose 作为 CI；**不**改登录状态机或 Cookie `Secure`；**不**做 Playwright；**不**标 `GATE-P0 verified`。
- **影响模块**：M08（next.config 与 proxy 辅助）；M09/M10（只消费同源 `/api/v1`，本切片不改页面）；M11（证据与进度）。
- **兼容方案**：既有 Fake fetch E2E 仍打 `/api/v1`；未设 origin 时行为与现在一致（无后端则 404）。
- **测试 ID**：`test_FR_AUTH_001_web_api_base_stays_same_origin`、`test_FR_AUTH_001_next_rewrites_api_v1_to_injected_origin`、`test_FR_AUTH_001_next_config_wires_injected_origin`、`test_NFR_OBS_next_rewrites_omitted_when_origin_missing`、`test_NFR_SEC_next_proxy_rejects_non_http_origin`、`test_GATE_P0_005_not_verified_by_next_rewrite`。
- **是否触发 ADR**：否（传输装配，不改状态机、权限、引用/删除语义、模型或检索配置）。
- **审核结果**：2026-09-09 Wave 3 主线会话 **批准**。

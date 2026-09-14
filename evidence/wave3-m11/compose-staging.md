# dev-staging Compose overlay（ND-STG-04）

环境：根 `docker-compose.yml` + overlay `docker-compose.staging.yml`；`ops/nginx/staging.conf`；`ops/compose.staging.env.example`。CI 不 `docker build` / `docker compose up`；本切片**未 SSH**、**未改安全组**、**未挂数据盘**、**未打 live 供应商**。

- nginx 钉 `nginx:1.26.3-alpine`，profile `app`，只反代 `web:3000`；默认 `${PIVOT_STAGING_HTTP_BIND:-127.0.0.1}:80:80`（SSH 隧道）。本切片不挂 443。
- overlay 为 postgres/minio/qdrant/redis/api/web/worker/nginx 补 `restart: unless-stopped`、json-file 日志轮转与 `deploy.resources` limits/reservations。limits 总和 ≤ 6GiB，给 8GiB 主机留 OS 余量；**fixture，不是冻结的 `TBD-P0`，不是 `NFR-CAP-006` 已验证规格**。yml 不写 `4C8G`。
- 不自建 MinerU / LLM / Embedding / Rerank；外部模型只走已注入 HTTP 变量。example 占位 `hash` / `local`，禁止提交供应商 URL 或密钥。
- 服务器 env 副本 gitignore；Runbook 列出 Owner SSH / 安全组 / 磁盘 / 域名前置。ECS apply 不由本切片冒充完成。
- `implemented`（overlay 文件）≠ `verified`。

| ID | 状态 | 原因 |
|---|---|---|
| NFR-CAP-006 | 未冻结 | 8GiB limits 为 staging fixture，不是容量实测，不是已冻生产规格 |
| GATE-P0-007 | unverified | 无 ECS 峰值 / 5 并发问答 / 100k 索引压测；P95 仍 TBD-P0 |
| GATE-P0-008 | unverified | overlay/runbook 入库 ≠ 固定版本发布、健康门禁和回滚演练；未 SSH、未改安全组 |

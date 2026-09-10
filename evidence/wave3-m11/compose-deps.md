# Wave 3 M11 依赖 Compose 切片限制

环境：本地可选 `docker compose up`；CI 不启动 Compose；不连接真实企业数据。

- 已提交 `docker-compose.yml`：postgres / minio / qdrant / redis，镜像钉死，端口绑 `127.0.0.1`。
- 本文件只覆盖依赖 fixture。api / web / worker Compose 服务见 `compose-api.md`、`compose-web.md`、`compose-worker.md`。
- 依赖 fixture 本身不提供应用 `/healthz`。
- Compose 依赖文件不等于发布、回滚或健康门禁通过。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-008 | unverified | 仅有依赖 fixture；无固定生产发布、无回滚演练 |

`implemented`（compose fixture）≠ `verified`。

# Wave 3 M11 应用健康端点限制

环境：FastAPI TestClient；不启动 Compose；不挂 `/api/v1`。

- `GET /healthz` 只表示进程存活，不探测依赖。
- `GET /readyz` 对注入的 postgres/minio/qdrant/redis 探测失败闭环；未注入探测则为 not_ready。
- 无固定生产发布、无回滚演练、无运行中的 api Compose 服务。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-008 | unverified | 仅有进程内健康装配；不等于固定版本发布、健康门禁和回滚已通过 |

`implemented`（/healthz /readyz）≠ `verified`。

# Wave 3 M03 MinIO ObjectStore 客户端限制

环境：`MinioObjectStore` 默认 CI 用注入的内存 client 子集；Compose MinIO 为 opt-in（`PIVOT_REQUIRE_COMPOSE=1` 且安装 `api[minio]`）。不启动 uvicorn；不把内存 client 标成生产对象存储。

- `PIVOT_OBJECT_STORE=minio` 将文档对象端口接到 `MinioObjectStore`；endpoint/bucket/密钥必须注入，禁止写死生产地址。
- 导出对象仍为 memory + `PublicDownloadSigner`；HTTP 预览/下载不返回 MinIO presign。
- `/readyz` 在仅接通 minio 探测时仍因 postgres/qdrant/redis 失败闭环。
- 无 Qdrant/Redis 客户端，无删除下线与索引原子发布。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | 对象存储客户端不等于状态一致性、幂等、删除与索引原子发布已通过 |

`implemented`（object store）≠ `verified`。

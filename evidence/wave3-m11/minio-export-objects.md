# Wave 3 M11 导出对象 MinIO 接线限制

环境：`PIVOT_OBJECT_STORE=minio` 时文档与导出字节共用注入的 MinIO client/bucket；公开下载仍为 `PublicDownloadSigner`。CI 用内存 client 子集。

- 导出 `put/get` 走 `ExportObjectAdapter`；`presign` 失败闭环，禁止 MinIO 预签名公开 URL。
- HTTP `GET /exports/{id}` 的 `download_url` 不暴露 endpoint/密钥/`storage_key`。
- 无对象字节下载 HTTP；导出任务仍为内存 repository。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | 导出字节落 MinIO 不等于状态一致性、幂等、删除与索引原子发布已通过 |

`implemented`（export object store）≠ `verified`。

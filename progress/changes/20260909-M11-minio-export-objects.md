# 变更申请：M11 导出对象接到 MinIO（仍用 PublicDownloadSigner）

- **日期**：2026-09-09
- **申请人**：Wave 3 主线会话（M11 composition root + M06 只消费 ObjectStorePort）
- **背景**：`PIVOT_OBJECT_STORE=minio` 已把**文档**对象接到 `MinioObjectStore`；导出仍为 `MemoryExportObjects`。SPEC §2.1 规定 MinIO 存原文/中间物/**导出物**。FR-EXPORT-001 要求短时公开 URL 不得暴露 MinIO 内部地址；既有 `PublicDownloadSigner` 不得改为 `ObjectStore.presign`。
- **原契约/现状**：
  - 文档 `MinioObjectStore` 可注入；导出 `ObjectStorePort.put/get/exists/presign` 由 M06 消费，HTTP 状态接口只返回 signer URL；
  - composition root 在 minio 模式下仍 `MemoryExportObjects(export_public_base)`；
  - 单元/安全测试断言 `presign_calls == []`。
- **拟变更内容**（本切片）：
  - M11：`PIVOT_OBJECT_STORE=minio` 时，导出对象与文档共用注入的 MinIO client/bucket；经 `ExportObjectAdapter` 满足导出端口：`put/get/exists` 转发，**`presign` 失败闭环**（禁止用 MinIO presign 做公开下载）；
  - 公开 `download_url` 仍由 `PublicDownloadSigner` 签发；响应不得含 `storage_key` / endpoint / 密钥；
  - `get` 缺失时按导出端口抛错（不把 `None` 当文件体）；
  - 默认 `PIVOT_OBJECT_STORE=memory` 行为不变；
  - **不** 新增独立导出 bucket 环境变量；**不** 增加对象字节下载 HTTP；**不** 把 `GATE-P0-003` 标 verified。
- **影响模块**：M11（bootstrap/adapter、pipeline 测试、证据）；M06（只消费端口）；M03（既有 MinIO 适配）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：Fake HTTP 导出测试与单元 `presign_calls` 断言不变；CI 仍用内存 MinIO client 子集。
- **测试 ID**：`test_NFR_OBS_runtime_minio_wires_export_object_store`、`test_FR_EXPORT_001_runtime_minio_export_bytes_roundtrip`、`test_FR_EXPORT_001_runtime_minio_download_url_does_not_leak_endpoint`、`test_FR_EXPORT_001_runtime_minio_export_presign_is_forbidden`。
- **是否触发 ADR**：否（不改变导出状态机、授权或引用/删除语义；不把 MinIO presign 当公开下载；不冻结 TBD-P0 TTL）。
- **审核结果**：2026-09-09 Wave 3 主线会话 **批准**。

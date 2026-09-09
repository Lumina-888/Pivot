# 问枢 Pivot 会话交接清单

> **日期**：2026-09-09  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**Redis 队列/缓存客户端**（配置注入，禁止写死生产 URL；Redis 不是事实源），或 Golden Set / 性能门禁。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / composition root / 存储客户端标成 `GATE-P0 verified`。

## 1. 产品现状

Python **278 passed / 7 skipped**；web foundation **15**。用户事实可走 SQLAlchemy；文档字节可走 MinIO 适配；向量可走 Qdrant 适配；其余仍是内存适配，不是可上线系统。

- `PIVOT_STORAGE=postgres` + `PIVOT_DATABASE_URL` 装配 `SqlAlchemyUserDirectory`
- `PIVOT_OBJECT_STORE=minio` + endpoint/bucket/密钥装配文档 `MinioObjectStore`
- `PIVOT_VECTOR_STORE=qdrant` + endpoint/collection 装配 `QdrantVectorStore`
- 检索仍 Fake KeywordRetriever；导出仍 memory + `PublicDownloadSigner`
- 分组 CI **不**启动 uvicorn/Next/Compose
- GATE-P0 全部 unverified；未打 `wave-3-integrated`

## 2. 已知缺口（按优先级）

1. 无真实 Redis 客户端；导出对象仍为 memory；检索未接 Qdrant
2. 无 Golden Set / 5 并发 / 备份恢复
3. PATCH `/admin/users/{id}` 只改 status；登录限流空操作；`must_change_password` 不入库
4. 无 Dockerfile / Compose api·web·worker

## 3. 下一刀建议

Qdrant payload 与 VectorStore SDK 适配已接线（CI 用内存 client）。下一刀实现 Redis Cache/Queue（非事实源），或 Golden Set / 性能门禁。

## 4. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。

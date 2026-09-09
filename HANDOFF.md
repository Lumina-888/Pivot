# 问枢 Pivot 会话交接清单

> **日期**：2026-09-09  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**Golden Set / 性能门禁**，或导出对象 MinIO / 检索接 Qdrant。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / composition root / 存储客户端标成 `GATE-P0 verified`。

## 1. 产品现状

Python **291 passed / 8 skipped**；web foundation **15**。四类存储均可注入客户端（CI 默认内存 client），不是可上线系统。

- `PIVOT_STORAGE=postgres` + `PIVOT_DATABASE_URL` 装配 `SqlAlchemyUserDirectory`
- `PIVOT_OBJECT_STORE=minio` 装配文档 `MinioObjectStore`（导出仍 memory）
- `PIVOT_VECTOR_STORE=qdrant` 装配 `QdrantVectorStore`（检索仍 Fake）
- `PIVOT_CACHE_STORE` / `PIVOT_QUEUE_STORE=redis` 装配 Redis 缓存/队列（登录限流仍内存）
- 分组 CI **不**启动 uvicorn/Next/Compose
- GATE-P0 全部 unverified；未打 `wave-3-integrated`

## 2. 已知缺口（按优先级）

1. 检索未接 Qdrant；导出对象仍 memory；登录限流未接 Redis；无 Celery
2. 无 Golden Set / 5 并发 / 备份恢复
3. PATCH `/admin/users/{id}` 只改 status；`must_change_password` 不入库
4. 无 Dockerfile / Compose api·web·worker

## 3. 下一刀建议

存储客户端切片已齐。下一刀做 Golden Set / 性能门禁，或把检索接到 Qdrant、导出对象接到 MinIO。

## 4. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。

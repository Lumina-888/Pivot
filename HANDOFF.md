# 问枢 Pivot 会话交接清单

> **日期**：2026-09-09  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**导出对象 MinIO / 检索接 Qdrant**，或 5 并发 / 备份恢复。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **296 passed / 8 skipped**；web foundation **15**。四类存储可注入客户端；Golden Set 仅有 10 条合成检索样本。

- `PIVOT_STORAGE=postgres` / `PIVOT_OBJECT_STORE=minio` / `PIVOT_VECTOR_STORE=qdrant` / Redis cache·queue 均可装配
- 文档对象可接 MinIO；**导出对象仍 memory**
- 检索仍 Fake KeywordRetriever；合成 Golden Set 只做标签断言
- GATE-P0 全部 unverified；未打 `wave-3-integrated`

## 2. 已知缺口（按优先级）

1. 检索未接 Qdrant；导出对象仍 memory；登录限流未接 Redis；无 Celery
2. Golden Set 未达 100~150；无 5 并发 / 备份恢复
3. PATCH `/admin/users/{id}` 只改 status；`must_change_password` 不入库
4. 无 Dockerfile / Compose api·web·worker

## 3. 下一刀建议

合成 Golden Set 夹具已立。下一刀把导出对象接到 MinIO（仍走 `PublicDownloadSigner`），或把检索接到 Qdrant（不冻结 k/距离）。

## 4. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。

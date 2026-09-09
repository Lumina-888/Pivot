# 问枢 Pivot 会话交接清单

> **日期**：2026-09-09  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**检索接 Qdrant**（不冻结 k/距离），或 5 并发 / 备份恢复。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **301 passed / 8 skipped**；web foundation **15**。四类存储可注入客户端；导出字节可走 MinIO，公开 URL 仍为 signer。

- `PIVOT_OBJECT_STORE=minio` 装配文档 **与导出** 对象；`presign` 不做公开下载
- 检索仍 Fake KeywordRetriever；Golden Set 仅 10 条合成样本
- GATE-P0 全部 unverified；未打 `wave-3-integrated`

## 2. 已知缺口（按优先级）

1. 检索未接 Qdrant；登录限流未接 Redis；无 Celery；导出任务仍内存
2. Golden Set 未达 100~150；无 5 并发 / 备份恢复
3. PATCH `/admin/users/{id}` 只改 status；`must_change_password` 不入库
4. 无 Dockerfile / Compose api·web·worker

## 3. 下一刀建议

导出对象已接到 MinIO。下一刀把检索接到 Qdrant（Fake KeywordRetriever 换为 VectorStore 消费，不冻结 TBD-P0），或 5 并发 / 备份恢复。

## 4. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。

# 问枢 Pivot 会话交接清单

> **日期**：2026-09-09  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**真实存储客户端**（PG/MinIO 等），或 Golden Set / 性能门禁。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / composition root / Next rewrite / opt-in Playwright 标成 `GATE-P0 verified`。

## 1. 产品现状

Python **247 passed / 4 skipped**；web foundation **15**。仍是内存适配为主，不是可上线系统。

- composition root + Next `/api/v1` rewrite 已通
- Playwright 登录为 **opt-in**：`python ops/run_playwright_login.py`（需 `pip install -e ./api[playwright]` 且 `playwright install chromium`）
- 分组 CI **不**启动 uvicorn/Next/Compose
- GATE-P0 全部 unverified；未打 `wave-3-integrated`

## 2. 已知缺口（按优先级）

1. 无真实 PG/MinIO/Qdrant/Redis 客户端
2. 无 Golden Set / 5 并发 / 备份恢复
3. PATCH `/admin/users/{id}` 只改 status；登录限流空操作
4. 无 Dockerfile / Compose api·web·worker

## 3. 下一刀建议

真实存储客户端（先 PG 或 MinIO，仍走端口、禁止写死生产 URL）。

## 4. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。

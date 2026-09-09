# 问枢 Pivot 会话交接清单

> **日期**：2026-09-09  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**MinIO ObjectStore 客户端**（注入 endpoint/bucket，禁止写死生产 URL），或 Golden Set / 性能门禁。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / composition root / Next rewrite / opt-in Playwright / PG 用户目录标成 `GATE-P0 verified`。

## 1. 产品现状

Python **256 passed / 5 skipped**；web foundation **15**。用户事实可走 SQLAlchemy；其余仍是内存适配，不是可上线系统。

- composition root + Next `/api/v1` rewrite 已通
- Playwright 登录为 **opt-in**：`python ops/run_playwright_login.py`
- `PIVOT_STORAGE=postgres` + `PIVOT_DATABASE_URL` 装配 `SqlAlchemyUserDirectory`
- 分组 CI **不**启动 uvicorn/Next/Compose
- GATE-P0 全部 unverified；未打 `wave-3-integrated`

## 2. 已知缺口（按优先级）

1. 无真实 MinIO/Qdrant/Redis 客户端；文档/导出字节仍为 memory
2. 无 Golden Set / 5 并发 / 备份恢复
3. PATCH `/admin/users/{id}` 只改 status；登录限流空操作；`must_change_password` 不入库
4. 无 Dockerfile / Compose api·web·worker

## 3. 下一刀建议

MinIO ObjectStore SDK 适配（实现 `pivot.storage.protocols.ObjectStore` / 文档 `ObjectStore`；配置注入；CI 默认不连真实 MinIO）。

## 4. 纪律（未改）

聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准。

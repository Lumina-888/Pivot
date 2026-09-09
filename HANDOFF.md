# 问枢 Pivot 会话交接清单

> **日期**：2026-09-09  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**Playwright 浏览器登录**，或真实存储客户端。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP / composition root / Next rewrite 标成 `GATE-P0 verified`。

## 1. 工作区与流程

| 项 | 结论 |
|---|---|
| 开发方式 | 已从并行 worktree 改为**主线串行**（`MODULE-SPEC-1.1`，变更 `progress/changes/20260908-M00-mainline-development.md`） |
| 唯一工作区 | `E:/AI Project/Pivot` |
| 历史 `Pivot-Mxx-*` | 22 个模块分支**早已合入 main**；Owner 已用 `git worktree remove` 拆掉；禁止再从那些目录拷文件 |
| 一次切片 | 可跨多个模块路径，须在进度里写明 Accountable |

## 2. 产品现状（观感 vs 事实）

Python **245 passed / 2 skipped**；`npm --prefix web test` **15 passed**。测的是内存适配 + TestClient + Next rewrite 配置，不是可上线系统。

| 层 | 实际 |
|---|---|
| HTTP | composition root 可 `uvicorn pivot.http.main:app --factory`；默认 `create_app()` 只健康检查 |
| 前端 | 浏览器仍 `fetch("/api/v1/...")`；Next 把 `/api/v1/:path*` rewrite 到注入的 `PIVOT_API_ORIGIN`；未设 origin 则登录 404 |
| 存储 | 运行时默认 memory 端口；无 PG/MinIO/Qdrant/Redis SDK |
| GATE-P0 | 全部 `unverified` |

## 3. 已合入 main 的能力

- Wave 0–2 已打 `wave-0/1/2-integrated`
- Wave 3：Compose fixture、健康检查、认证/文档/搜索/Run/SSE/导出/会话 HTTP、预览下载、composition root、Next `/api/v1` 反代
- **未打** `wave-3-integrated`

## 4. 已知缺口（按优先级）

1. **无 Playwright**：rewrite 配置已测，浏览器登录未测
2. PATCH `/admin/users/{id}` 只改 `status`
3. 登录限流空操作
4. 密码哈希双轨：runtime Argon2id，HTTP 流水线测试 PBKDF2
5. 无真实 MinIO/PG、无 Dockerfile/Compose api·web

## 5. 下一刀建议

1. Playwright 打通登录页 → `/api/v1/auth/login`（需同时起 Next + uvicorn，CI 仍默认不 up）
2. 或真实存储客户端

本地联调：`web/.env.example` → `web/.env.local` 设 `PIVOT_API_ORIGIN=http://127.0.0.1:8000`，再 `next dev` + `uvicorn pivot.http.main:app --factory`。

## 6. 纪律（未改）

- SDD + TDD；测试名 `test_<requirement_id>_<behavior>()`
- 不私设 `TBD-P0`，不交密钥
- 聊天记录不是项目事实

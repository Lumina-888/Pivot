# 问枢 Pivot 会话交接清单

> **日期**：2026-09-08  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**预览/下载 HTTP**（M02 领域 + M11 挂载）。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP 标成 `GATE-P0 verified`。

## 1. 工作区与流程

| 项 | 结论 |
|---|---|
| 开发方式 | 已从并行 worktree 改为**主线串行**（`MODULE-SPEC-1.1`，变更 `progress/changes/20260908-M00-mainline-development.md`） |
| 唯一工作区 | `E:/AI Project/Pivot` |
| 历史 `Pivot-Mxx-*` | 22 个模块分支**早已合入 main**；Owner 已用 `git worktree remove` 拆掉；禁止再从那些目录拷文件 |
| 还可能残留 | `E:/AI Project/.pytest_cache`（测试缓存，可手动删） |
| 一次切片 | 可跨多个模块路径，须在进度里写明 Accountable |

## 2. 产品现状（观感 vs 事实）

测试约 **227 passed / 2 skipped** 是真的，测的是 **内存 Fake + TestClient**，不是可上线系统。

| 层 | 实际 |
|---|---|
| HTTP | `create_app()` 注入才挂路由；无 `main.py` / Dockerfile / Compose 中的 api·web·worker |
| 存储 | SQLAlchemy/Alembic 在；Auth/文档/导出/会话 HTTP 走内存 fake；MinIO/Qdrant/Redis 无 SDK 客户端 |
| 检索 | 搜索 HTTP 为内存子串匹配；dense/BM25 为 `KeywordRetriever` |
| 问答 | 把命中 chunk 用 `。` 拼接；无 LLM / LangGraph |
| Worker | 正则抽 PDF + `FakeEmbedding`；非 Celery |
| SSE | 内存 EventLog 补发，非长连接 |
| 前端 | 10 页路由在，`fetch("/api/v1/...")`；Next **无** rewrite/proxy，本地登录会 404 |
| GATE-P0 | 全部 `unverified`；`implemented` ≠ `verified` |

## 3. 已合入 main 的能力（Wave 0–3 切片）

- Wave 0–2 已打 `wave-0/1/2-integrated`
- Wave 3 已合入：Compose 依赖 fixture、`/healthz` `/readyz`、认证、文档上传/列表/详情/重试/删除、搜索、Run/SSE、导出/审计、改密/管理用户、会话 CRUD
- **未打** `wave-3-integrated`
- main 合并终点（会话 CRUD 文档）：`b45fead`；其后主线协议文档可能尚未 commit

## 4. 已知缺口 / 缺陷（按优先级）

1. **没有 composition root**：无法 `uvicorn` 拉起真实装配
2. **前端未接到后端**：缺 Next 反代 `/api/v1`
3. **PATCH `/admin/users/{id}`**：请求体允许 `role` / `reset_password`，实现只改 `status`，否则 404
4. **登录限流空操作**：`InMemoryAttempts.is_blocked` 恒为 `False`
5. **密码哈希双轨**：有 `Argon2idHasher`，HTTP 流水线用测试 PBKDF2
6. **无预览/下载 HTTP**（当前下一刀）
7. 无 Playwright、无真实 dense/BM25、无对象字节下载、无 PG/MinIO 客户端

## 5. 下一刀建议

不要再加一条只在 TestClient 里绿的路由就当 Wave 3 完成。杠杆顺序：

1. composition root（可启动 FastAPI，Argon2 + 可切换存储）
2. Next 反代 `/api/v1`，登录页能通
3. 预览/下载 HTTP
4. 再考虑 Playwright / 真实检索

若仍按 `PROGRESS.md` 字面执行：先做第 3 项预览/下载。新会话应向 Owner 确认是否改为先做 1–2。

## 6. 纪律（未改）

- SDD + TDD：Red → Contract → Green → Refactor → Integration → Regression
- 测试名：`test_<requirement_id>_<behavior>()`
- 不私设 `TBD-P0`，不交密钥/企业文档/供应商 URL
- 不为修绿关闭授权、过滤、幂等、审计
- 聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准

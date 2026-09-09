# 问枢 Pivot 会话交接清单

> **日期**：2026-09-09  
> **性质**：聊天结论压缩。需求仍以 `SPEC.md` 为准，进度以 `PROGRESS.md` 为准，协作以 `MODULE_SPEC.md` 1.1 / `AGENTS.md` 为准。  
> **本文件不是规范源。**

## 0. 新会话 60 秒恢复

1. 工作区：`E:/AI Project/Pivot`，分支：`main`。不要新建 worktree。
2. 读：`AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → 本文件。
3. 下一刀：**Next 反代 `/api/v1`**（登录页能通），随后 Playwright / 真实存储客户端。
4. 不要冻结 `TBD-P0`，不要把 Fake HTTP 或 composition root 标成 `GATE-P0 verified`。

## 1. 工作区与流程

| 项 | 结论 |
|---|---|
| 开发方式 | 已从并行 worktree 改为**主线串行**（`MODULE-SPEC-1.1`，变更 `progress/changes/20260908-M00-mainline-development.md`） |
| 唯一工作区 | `E:/AI Project/Pivot` |
| 历史 `Pivot-Mxx-*` | 22 个模块分支**早已合入 main**；Owner 已用 `git worktree remove` 拆掉；禁止再从那些目录拷文件 |
| 还可能残留 | `E:/AI Project/.pytest_cache`（测试缓存，可手动删） |
| 一次切片 | 可跨多个模块路径，须在进度里写明 Accountable |

## 2. 产品现状（观感 vs 事实）

测试约 **245 passed / 2 skipped** 是真的，测的是 **内存适配 + TestClient**，不是可上线系统。

| 层 | 实际 |
|---|---|
| HTTP | `create_app()` 默认只健康检查；`assemble_runtime_app` / `uvicorn pivot.http.main:app --factory` 挂全部已有 `/api/v1`；无 Dockerfile / Compose api·web·worker |
| 存储 | SQLAlchemy/Alembic 在；运行时默认 memory 端口；MinIO/Qdrant/Redis 无 SDK 客户端 |
| 检索 | 搜索 HTTP 为内存子串匹配；dense/BM25 为 `KeywordRetriever` |
| 问答 | 把命中 chunk 用 `。` 拼接；无 LLM / LangGraph |
| Worker | 正则抽 PDF + `FakeEmbedding`；非 Celery |
| SSE | 内存 EventLog 补发，非长连接 |
| 前端 | 10 页路由在，`fetch("/api/v1/...")`；Next **无** rewrite/proxy，本地登录会 404 |
| GATE-P0 | 全部 `unverified`；`implemented` ≠ `verified` |

## 3. 已合入 main 的能力（Wave 0–3 切片）

- Wave 0–2 已打 `wave-0/1/2-integrated`
- Wave 3 已合入：Compose 依赖 fixture、`/healthz` `/readyz`、认证、文档上传/列表/详情/重试/删除/预览/下载、搜索、Run/SSE、导出/审计、改密/管理用户、会话 CRUD、composition root
- **未打** `wave-3-integrated`
- 主线协议：`ff1626a`（MODULE-SPEC-1.1）；composition root 见 `PROGRESS.md`

## 4. 已知缺口 / 缺陷（按优先级）

1. **前端未接到后端**：缺 Next 反代 `/api/v1`
2. **PATCH `/admin/users/{id}`**：请求体允许 `role` / `reset_password`，实现只改 `status`，否则 404
3. **登录限流空操作**：`InMemoryAttempts.is_blocked` 恒为 `False`
4. **密码哈希双轨**：composition root 用 Argon2id；HTTP 流水线测试仍用 PBKDF2
5. 预览/下载 HTTP 已挂（内存对象字节；无真实 MinIO）
6. 无 Playwright、无真实 dense/BM25、无导出对象字节下载、无 PG/MinIO 客户端、无 Dockerfile/Compose api

## 5. 下一刀建议

不要再加一条只在 TestClient 里绿的路由就当 Wave 3 完成。杠杆顺序：

1. Next rewrite/proxy 使 `/api/v1` 从 web 应用可达，登录页能通
2. 再考虑 Playwright / 真实检索 / 真实 MinIO

composition root 已完成。下一刀默认第 1 项 Next 反代。

## 6. 纪律（未改）

- SDD + TDD：Red → Contract → Green → Refactor → Integration → Regression
- 测试名：`test_<requirement_id>_<behavior>()`
- 不私设 `TBD-P0`，不交密钥/企业文档/供应商 URL
- 不为修绿关闭授权、过滤、幂等、审计
- 聊天记录不是项目事实；以 commit / tag / `PROGRESS.md` / 测试证据为准

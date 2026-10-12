# ND-GAP-01 后台指标路由交接

**日期**: 2026-10-12  
**仓库**: `/home/lumina888/Projects/Pivot`  
**分支**: `main`  
**已提交基线**: `aa44cb8`  
**下一会话焦点**: 不私开被契约阻塞的票；先核对进度文档与票状态是否一致，再等 03-A / 04-A 签认后继续 Agent 主线。

## 本轮做了什么

实现并提交 ND-GAP-01 的最小 HTTP 面：

- `6bb7e9d` `feat(M11): 实现 /admin/metrics 和 /admin/tasks HTTP 路由 [ND-GAP-01]`
- `aa44cb8` `docs(M00): 更新 PROGRESS.md 记录 ND-GAP-01 完成状态`

变更记录：`progress/changes/20261012-M11-admin-metrics-tasks.md`  
测试：`tests/integration/pipeline/test_ND_GAP_01_admin_metrics_tasks.py`（6 passed）

路由行为：

- `GET /api/v1/admin/metrics`：系统/QA/文档/存储结构；缺探针或统计时给默认值。
- `GET /api/v1/admin/tasks`：`tasks: []`、`pagination: null`。任务事实源未接，留给 M07。
- 未认证 401 `AUTH_INVALID_CREDENTIALS`；非管理员 403 `AUTH_FORBIDDEN`。错误体是顶层 `code`，不是 `error.code`。

实现位置：

- `api/src/pivot/http/admin.py`
- `api/src/pivot/http/app.py` 在 auth 存在时挂载
- `DocumentService.count_*` 使用 `list_active()`
- `RunService.count_*` 读内存 store

本轮 ruff 针对改动文件通过。未跑完整分组回归，未宣称 GATE。

## 不要当成已完成

- 指标不是持久化统计，分页与阈值仍是 TBD-P0。
- `/admin/tasks` 不是真实队列。
- 票表 `progress/tickets/spec-1.1-remaining.md` 仍把 ND-GAP-01 标为 blocked（M00 字段/分页/路径所有权）。PROGRESS 已写成路由已挂。下一会话先核对这两处，不要把 HTTP 绿灯写成 Contract 关闭。
- 根交接 `HANDOFF.md` 仍写 `/admin/metrics` `/admin/tasks` 未挂，且基线停在 `d7c8eca`。它落后于 `aa44cb8`。

## 未提交

`api/src/pivot/http/app.py` 仅有 documents router 调用的折行格式化（`git diff` 可见）。不是功能改动。不要提交，除非下一会话确认要单独做格式清理。

## 阻塞（不要提前做）

票状态以 `progress/tickets/spec-1.1-remaining.md` 为准。HANDOFF 明确：03-E 的公开 resume 必须等 03-A 发布；04 等 DR-011 与真实 PG。

仍 blocked、本轮未开工：

- ND-GAP-02 持久审计（要 M03 Repository/迁移 Contract）
- ND-GAP-03 首次改密生命周期（不得私加 `must_change_password`）
- ND-GAP-04 签名下载端到端（不得新公开对象字节路由）
- ND-AGENT-03-E、04-B 及之后

历史交接 `.pi/handoffs/20261012-02-abc-signoff-complete.md` 记录 02-A/B/C 消费者签认，但当前 `PROGRESS.md` / `HANDOFF.md` 仍写 review 与 0 ready。下一会话不要用旧 handoff 覆盖现行进度文档。

## 恢复

```bash
cd /home/lumina888/Projects/Pivot
git switch main
git log --oneline --decorate -8
git status --short
source .venv/bin/activate
python -m pytest tests/integration/pipeline/test_ND_GAP_01_admin_metrics_tasks.py -q
```

先读 `AGENTS.md`、`PROGRESS.md`、`HANDOFF.md`、`progress/tickets/spec-1.1-remaining.md`。

## Suggested skills

- 继续改模块边界或接口时：`codebase-design`
- 若下一会话要按测试先补行为：`tdd`
- 若要审查 `aa588ca..aa44cb8`：`code-review`
- 若测试或运行失败：`diagnosing-bugs`
- 若只是在仓库里找符号/调用点：`pi-lens-lsp-navigation`、`pi-lens-ast-grep`

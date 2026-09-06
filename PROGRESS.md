# 问枢 Pivot 开发进度

> **进度文档不是需求源**：需求以 [`SPEC.md`](SPEC.md) 为准，模块边界以 [`MODULE_SPEC.md`](MODULE_SPEC.md) 为准。  
> **最后更新**：2026-09-06  
> **当前状态**：Wave 0 已完成退出评审；基线 `wave-0-integrated`。
> **当前基线**：`wave-0-integrated`（M00 `contract-v0.1` + M03 数据端口 + M08 Web client 已冻结）。

## 1. 新会话恢复入口

1. 读取 `AGENTS.md`；
2. 读取 `MODULE_SPEC.md`；
3. 读取本文件和对应的 `progress/modules/Mxx.md`；
4. 用 `git log --oneline --decorate -20`、`git worktree list` 确认实际基线；
5. 只有满足模块 DoR 后，才在对应 `module/Mxx-*` worktree 开发。

如果没有指定模块：从 **Wave 1 的 M01、M02、M04、M05、M06、M07** 中选择一个尚未被其他会话认领的模块；基于 `wave-0-integrated` 创建 worktree，不要直接实现 Wave 2 页面。

## 2. 当前波次与模块状态

状态枚举：`planned` → `claimed` → `in_progress` → `blocked` → `review` → `integrated`；只有集成会话可将模块标记为 `integrated`。

| 模块 | 状态 | 分支/worktree | 会话/Owner | 基线契约 | 最近证据 | 下一步 |
|---|---|---|---|---|---|---|
| M00 契约治理 | integrated | `module/M00-contracts` / `../Pivot-M00-contracts` | 本会话已集成 | `contract-v0.1` | `tests/contract`: 48 passed | 已完成契约、场景、矩阵；依赖模块开始消费 |
| M01 身份授权 | planned | — | — | `contract-v0.1` | — | 可基于 `wave-0-integrated` 启动 |
| M02 文档接入 | planned | — | — | `contract-v0.1` | — | 可基于 `wave-0-integrated` 启动 |
| M03 数据基础 | integrated | `module/M03-data` / `../Pivot-M03-data` | 本集成会话 | `contract-v0.1` | M03 12 + M00 48 tests passed；Ruff/compile 通过 | PostgreSQL/外部存储集成待 M11 验证 |
| M04 检索 RAG | planned | — | — | `contract-v0.1` | — | 等待 M07 索引端口消费；可先用 Fake |
| M05 QA/Run/SSE | planned | — | — | `contract-v0.1` | — | 等待 M04；可先用 Fake 检索 |
| M06 导出/审计 | planned | — | — | `contract-v0.1` | — | 等待 M05 持久化答案/Run |
| M07 Worker/解析/索引 | planned | — | — | `contract-v0.1` | — | 可基于 M02 规则与 M03 端口启动 |
| M08 Web 基础 | integrated | `module/M08-web-foundation` / `../Pivot-M08-web-foundation` | 本集成会话 | `contract-v0.1` | M08 9 tests + typecheck/lint 通过 | M09/M10 消费共享组件与 client |
| M09 员工前台 | planned | — | — | `contract-v0.1` | — | 等待 Wave 1 契约与可运行 fixture |
| M10 管理后台 | planned | — | — | `contract-v0.1` | — | 等待 Wave 1 契约与可运行 fixture |
| M11 集成/质量/运维 | planned | — | — | `wave-0-integrated` | Wave 0 回归 69 passed | 等待 Wave 1 模块交付 |

模块详细状态由各自 `progress/modules/Mxx.md` 维护；模块会话不要并发编辑本表。

## 3. 需求追踪摘要

完整映射和 Accountable/Contributors 见 [`MODULE_SPEC.md §8`](MODULE_SPEC.md#8-需求-accountable-映射)。验收链必须遵循：需求 ID → 场景 ID → 契约/数据 → 测试 ID → 验收证据 → verified。

| 需求范围 | Accountable | 测试/场景入口 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| FR-AUTH-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/`、`spec/scenarios/auth.feature` | planned | M00 contract-v0.1 已提供，待实现 |
| FR-RBAC-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/`、`spec/scenarios/auth.feature` | planned | M00 contract-v0.1 已提供，待实现 |
| FR-DOC-001~008 | M02 | `tests/unit/documents/` | planned | 待实现 |
| FR-SEARCH-001~002 / FR-RAG-001~006 | M04 | `tests/unit/retrieval/` | planned | 待实现 |
| FR-QA-001~006 / FR-STREAM-001~005 | M05 | `tests/unit/qa/`、`tests/contract/stream/` | planned | 待实现 |
| FR-EXPORT-001~003 / FR-AUDIT-001~003 | M06 | `tests/unit/exports/`、`tests/unit/audit/` | planned | 待实现 |
| §2 存储不变量 | M03 | `tests/integration/db/`、`api/src/pivot/db/`、`migrations/` | implemented | M03 12 项测试 + 48 项 M00 契约回归通过；PostgreSQL 真实环境待 M11 |
| §6 解析/分块/索引执行 | M07 | `tests/unit/worker/`、`tests/integration/worker/` | planned | 待实现 |
| §1.5 / NFR-UX 设计系统与 client | M08 | `tests/e2e/fixtures/web/test-foundation.mjs` | implemented | M08 9 项基础测试通过；产品页面待 M09/M10 |
| 10 页 UI | M09/M10 | `tests/e2e/user/`、`tests/e2e/admin/` | planned | 待实现 |
| NFR-CAP/PERF/OBS/DR、GATE-P0-001~008 | M11 | `tests/security/`、`tests/performance/`、`evidence/` | planned | 待实现 |

## 4. 当前波次计划

### Wave 0 — 基线冻结（已完成）

- [x] M00：从 SPEC §5、附录 B/C 建立并集成 `contract-v0.1` 草案（48 项契约测试通过）；
- [x] M03：建立数据对象、Repository/UoW 和 PG/MinIO/Qdrant/Redis adapter 接口草案；12 项 M03 测试与 48 项 M00 回归通过；
- [x] M08：建立 Next.js/TypeScript 工程、S3 设计系统和 API/SSE client 边界（9 项基础测试通过）；
- [x] Wave 0 退出评审：契约、数据接口、Web client 输入已冻结；三项所有权变更申请已批准；标签 `wave-0-integrated`。

### Wave 1 — 核心能力

M01、M02、M04、M05、M06、M07 并行；前置条件是 Wave 0 集成 tag。详见 `MODULE_SPEC.md §4.3`。

### Wave 2 — 页面与联调

M09、M10、M11 并行；依赖 Wave 1 契约和可运行 fixture。

### Wave 3 — P0/P1 门禁

M11 组织完整测试、Golden Set、性能、恢复和回滚；M00 汇总矩阵。

## 5. 未完成项与已知差距

- [x] Wave 0 基础已存在：`api/` 数据端口、`web/` 设计系统与 client；`worker/` 仍未实现；
- [x] `spec/contracts/`、`spec/scenarios/`、`spec/acceptance/matrix.md` 已由 M00 建立；Golden Set 和供应商 Fake 尚待对应模块建立；
- [x] `tests/` 已有 M00 契约 48、M03 数据 12、M08 基础 9；其余测试层仍为骨架；
- [ ] PostgreSQL/Qdrant/MinIO/Redis/Docker Compose 尚未建立；
- [ ] 所有 `TBD-P0` 均未冻结，禁止模块自行填默认值；
- [ ] P0 八项门槛均未验证；
- [x] Wave 0 三项变更申请已批准：`20260906-M00-contract-test-path.md`、`20260906-M03-ownership-clarification.md`、`20260906-M08-web-scaffold-ownership.md`。

## 6. 轮次日志

### 2026-09-06 — Wave 0 退出评审与 `wave-0-integrated`

- **完成**：非快进合并 `module/M08-web-foundation`（`1181e28`）；批准三项所有权变更并写入 `MODULE_SPEC.md`；创建 `wave-0-integrated`。
- **验证**（main，2026-09-06）：
  - `pytest tests/integration/db tests/contract -q` → **60 passed**（M03 12 + M00 48）；
  - `npm --prefix web ci && npm --prefix web test` → **9 passed**；
  - `npm --prefix web run typecheck`、`npm --prefix web run lint` → 通过。
- **退出条件核对**：
  - `contract-v0.1` 已冻结（OpenAPI/SSE/Worker + 48 项契约测试）；
  - 数据 adapter 协议已冻结（Repository/UoW、Object/Vector/Queue/Cache ports）；
  - Web API/SSE client 输入已冻结（`/api/v1`、错误包、SSE 事件白名单、`Last-Event-ID`）；
  - 公共路径所有权无歧义（三项变更申请已写入 MODULE_SPEC）；
  - M00/M03/M08 均有进度文件、模块 tag 与测试证据。
- **限制/不通过项**：未连接真实 PostgreSQL/MinIO/Qdrant/Redis；无浏览器 E2E；`web/app/page.tsx` 为装配页，M09 必须替换；`npm audit` 报告 Next 14.2.15 传递依赖漏洞，不在 Wave 0 静默升级；全部 `TBD-P0` 与 GATE-P0 仍未冻结/验证。
- **基线**：M08 模块提交 `2fac277`、标签 `M08-v0.1.0`；Wave 0 标签 `wave-0-integrated`。

### 2026-09-06 — M00 contract-v0.1 集成

- **完成**：合并 `module/M00-contracts`（merge commit 由本集成会话产生）；集成 OpenAPI、SSE、Worker schema、六组 Gherkin、验收矩阵及 48 项契约测试。
- **验证**：主分支运行 `tests/contract` → **48 passed**；M00 tags：`contract-v0.1`、`M00-v0.1.0`。
- **前置**：Wave 0 尚未完成，`wave-0-integrated` 需等待 M03/M08 交付后再创建。

### 2026-09-06 — M03 数据基础集成

- **完成**：以非快进方式合并 `module/M03-data`，集成 SQLAlchemy 模型、Alembic 初始迁移、UnitOfWork、Repository/存储端口、opaque ID/UTC 工具和审计追加写保护。
- **验证**：在 M03 worktree 环境运行 `tests/integration/db tests/contract` → **60 passed**；Ruff check 与 compileall 均通过。
- **限制**：尚未连接真实 PostgreSQL/MinIO/Qdrant/Redis；PostgreSQL 权限、partial index、审计触发器由 M11 后续验证。
- **基线**：M03 模块提交 `9a8e851`、标签 `M03-v0.1.0`；本次集成提交为当前 main HEAD。

### 2026-09-06 — MODULE-SPEC-1.0 建立

- **完成**：创建 `MODULE_SPEC.md`、`AGENTS.md`、本进度文档和 `progress/modules/` 模板；定义 M00–M11、依赖 DAG、Wave 0–3、文件 Owner、worktree、交接和门禁协议。
- **文档治理**：按用户确认，保留工作区对 `问枢Pivot-技术方案V2.md`、`问枢Pivot.txt` 的删除，并在 README 中说明历史可从 Git 恢复；不修改历史规格内容。
- **验证**：待文档链接、覆盖范围和 Git 差异检查；完成后创建 `module-spec-v1.0` 标签。
- **下一步**：选择 M00/M03/M08 中一个 Wave 0 模块，创建独立 worktree，先完成 DoR 和 Red/Contract 工作。
- **风险**：模块并行前必须先提交并冻结本基线；契约、数据库迁移、共享组件和根进度不可由多个会话并发修改。

## 7. TBD-P0 与 ADR 提醒

不要在本文件或模块进度中把以下内容伪装成已冻结事实：登录限流、上传资源限制、分块/检索/RRF/rerank 参数、超时/token/并发预算、分页、质量阈值、保留期限、RPO/RTO 等。任何改变状态机、权限、引用/删除语义、模型或检索配置的提案，都必须关联 SPEC 附录 E 的 ADR。

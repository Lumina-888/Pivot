# 问枢 Pivot 开发进度

> **进度文档不是需求源**：需求以 [`SPEC.md`](SPEC.md) 为准，模块边界以 [`MODULE_SPEC.md`](MODULE_SPEC.md) 为准。  
> **最后更新**：2026-09-06  
> **当前状态**：分模块并行开发规格已建立，尚未启动 Wave 0 实现。  
> **当前基线**：`module-spec-v1.0`（创建后打标）。

## 1. 新会话恢复入口

1. 读取 `AGENTS.md`；
2. 读取 `MODULE_SPEC.md`；
3. 读取本文件和对应的 `progress/modules/Mxx.md`；
4. 用 `git log --oneline --decorate -20`、`git worktree list` 确认实际基线；
5. 只有满足模块 DoR 后，才在对应 `module/Mxx-*` worktree 开发。

如果没有指定模块：先从 **Wave 0 的 M00、M03、M08** 中选择一个尚未被其他会话认领的模块，不要直接实现 Wave 1 业务代码。

## 2. 当前波次与模块状态

状态枚举：`planned` → `claimed` → `in_progress` → `blocked` → `review` → `integrated`；只有集成会话可将模块标记为 `integrated`。

| 模块 | 状态 | 分支/worktree | 会话/Owner | 基线契约 | 最近证据 | 下一步 |
|---|---|---|---|---|---|---|
| M00 契约治理 | planned | — | — | — | — | 生成契约来源映射，建立 contract-v0.1 |
| M01 身份授权 | planned | — | — | — | — | 等待 M00/M03 Wave 0 |
| M02 文档接入 | planned | — | — | — | — | 等待 M00/M03 Wave 0 |
| M03 数据基础 | planned | — | — | — | — | 建立模型、Repository、adapter 接口 |
| M04 检索 RAG | planned | — | — | — | — | 等待 M00/M03/M07 |
| M05 QA/Run/SSE | planned | — | — | — | — | 等待 M00/M03/M04 |
| M06 导出/审计 | planned | — | — | — | — | 等待 M00/M03/M05 |
| M07 Worker/解析/索引 | planned | — | — | — | — | 等待 M00/M02/M03 |
| M08 Web 基础 | planned | — | — | — | — | 建立 Next.js、S3 设计系统、client 边界 |
| M09 员工前台 | planned | — | — | — | — | 等待 M08 与 Wave 1 契约 |
| M10 管理后台 | planned | — | — | — | — | 等待 M08 与 Wave 1 契约 |
| M11 集成/质量/运维 | planned | — | — | — | — | 等待各模块交付 |

模块详细状态由各自 `progress/modules/Mxx.md` 维护；模块会话不要并发编辑本表。

## 3. 需求追踪摘要

完整映射和 Accountable/Contributors 见 [`MODULE_SPEC.md §8`](MODULE_SPEC.md#8-需求-accountable-映射)。验收链必须遵循：需求 ID → 场景 ID → 契约/数据 → 测试 ID → 验收证据 → verified。

| 需求范围 | Accountable | 测试/场景入口 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| FR-AUTH-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/` | planned | 待实现 |
| FR-RBAC-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/` | planned | 待实现 |
| FR-DOC-001~008 | M02 | `tests/unit/documents/` | planned | 待实现 |
| FR-SEARCH-001~002 / FR-RAG-001~006 | M04 | `tests/unit/retrieval/` | planned | 待实现 |
| FR-QA-001~006 / FR-STREAM-001~005 | M05 | `tests/unit/qa/`、`tests/contract/stream/` | planned | 待实现 |
| FR-EXPORT-001~003 / FR-AUDIT-001~003 | M06 | `tests/unit/exports/`、`tests/unit/audit/` | planned | 待实现 |
| §2 存储不变量 | M03 | `tests/integration/db/` | planned | 待实现 |
| §6 解析/分块/索引执行 | M07 | `tests/unit/worker/`、`tests/integration/worker/` | planned | 待实现 |
| 10 页 UI / NFR-UX | M08/M09/M10 | `tests/e2e/user/`、`tests/e2e/admin/` | planned | 待实现 |
| NFR-CAP/PERF/OBS/DR、GATE-P0-001~008 | M11 | `tests/security/`、`tests/performance/`、`evidence/` | planned | 待实现 |

## 4. 当前波次计划

### Wave 0 — 基线冻结（下一步）

- [ ] M00：从 SPEC §5、附录 B/C 建立 `contract-v0.1` 草案；
- [ ] M03：建立数据对象、Repository/UoW 和 PG/MinIO/Qdrant/Redis adapter 接口草案；
- [ ] M08：建立 Next.js/TypeScript/shadcn 工程和 S3 设计系统边界；
- [ ] 每个 Wave 0 模块创建自己的 worktree 和 `progress/modules/Mxx.md` 状态记录；
- [ ] Wave 0 退出评审：契约、数据接口、Web client 输入冻结。

### Wave 1 — 核心能力

M01、M02、M04、M05、M06、M07 并行；前置条件是 Wave 0 集成 tag。详见 `MODULE_SPEC.md §4.3`。

### Wave 2 — 页面与联调

M09、M10、M11 并行；依赖 Wave 1 契约和可运行 fixture。

### Wave 3 — P0/P1 门禁

M11 组织完整测试、Golden Set、性能、恢复和回滚；M00 汇总矩阵。

## 5. 未完成项与已知差距

- [ ] 真实 `api/`、`web/`、`worker/` 代码尚不存在；
- [ ] `spec/contracts/`、`spec/scenarios/`、Golden Set 和供应商 Fake 尚待对应模块建立；
- [ ] `tests/` 目前只有附录 D 目录骨架；
- [ ] PostgreSQL/Qdrant/MinIO/Redis/Docker Compose 尚未建立；
- [ ] 所有 `TBD-P0` 均未冻结，禁止模块自行填默认值；
- [ ] P0 八项门槛均未验证；
- [ ] `progress/changes/` 目前没有已批准的跨模块变更。

## 6. 轮次日志

### 2026-09-06 — MODULE-SPEC-1.0 建立

- **完成**：创建 `MODULE_SPEC.md`、`AGENTS.md`、本进度文档和 `progress/modules/` 模板；定义 M00–M11、依赖 DAG、Wave 0–3、文件 Owner、worktree、交接和门禁协议。
- **文档治理**：按用户确认，保留工作区对 `问枢Pivot-技术方案V2.md`、`问枢Pivot.txt` 的删除，并在 README 中说明历史可从 Git 恢复；不修改历史规格内容。
- **验证**：待文档链接、覆盖范围和 Git 差异检查；完成后创建 `module-spec-v1.0` 标签。
- **下一步**：选择 M00/M03/M08 中一个 Wave 0 模块，创建独立 worktree，先完成 DoR 和 Red/Contract 工作。
- **风险**：模块并行前必须先提交并冻结本基线；契约、数据库迁移、共享组件和根进度不可由多个会话并发修改。

## 7. TBD-P0 与 ADR 提醒

不要在本文件或模块进度中把以下内容伪装成已冻结事实：登录限流、上传资源限制、分块/检索/RRF/rerank 参数、超时/token/并发预算、分页、质量阈值、保留期限、RPO/RTO 等。任何改变状态机、权限、引用/删除语义、模型或检索配置的提案，都必须关联 SPEC 附录 E 的 ADR。

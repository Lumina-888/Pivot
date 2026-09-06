# 问枢 Pivot

企业私有文档检索问答（RAG）Web 系统。纯 Web 形态，MVP 固定 10 个页面，技术路线为 Next.js + FastAPI + PostgreSQL/MinIO/Qdrant/Redis + Celery（详见规格文档）。

> **当前状态：分模块并行开发基线（尚未启动 Wave 0）。** 本仓库目前包含规格文档、UI 静态原型、按 SPEC 附录 D 建立的工程骨架，以及并行开发治理文档；**尚无真实后端、前端、数据库、部署或测试代码**。
>
> 多会话开发入口：先读 [`AGENTS.md`](AGENTS.md)，再读 [`MODULE_SPEC.md`](MODULE_SPEC.md) 和 [`PROGRESS.md`](PROGRESS.md)。每个模块必须使用独立分支与 worktree；模块状态写入 `progress/modules/Mxx.md`，根进度由集成会话汇总。

## 文档层级（规格优先级见 SPEC §0.1）

| 文件 | 定位 |
|---|---|
| `SPEC.md` | **规范源**（SPEC-1.0）：SDD + TDD 开发总规格，需求 → 场景 → 契约 → 数据 → 测试 → 验收 |
| `MODULE_SPEC.md` | **分模块并行开发规范**（MODULE-SPEC-1.0）：边界、依赖、Owner、worktree、交接和集成门禁 |
| `AGENTS.md` | 新会话协作指令：启动检查、文件所有权、TDD、收尾交接 |
| `PROGRESS.md` | 版本化活进度：波次、模块状态、需求追踪、证据和下一步 |
| `技术方案GPT.md` | 工程实施增强基线（GPT-1.0） |
| `问枢Pivot-A3门户设计.md` | 门户交互细节基线 |
| `问枢Pivot-技术方案V2.md` | 产品范围与主要路线基线（当前工作区已删除，内容仍保留在 Git 历史） |
| `风格样稿/` | S3 完整原型：UI 信息架构/视觉/交互回归基线，**Mock 行为不等于生产能力**（SPEC §1.5） |

`SPEC.md` 中的 `TBD-P0` 数值为未冻结参数，实现人员**不得私自替换为未记录的"默认值"**（SPEC 引言、§0.6）。

## 目录结构

```text
SPEC.md                  规范源（根目录，保持既有相对引用不动）
MODULE_SPEC.md            分模块并行开发规范（M00–M11、Wave、Owner、worktree）
AGENTS.md / PROGRESS.md   新会话指令与版本化活进度
技术方案GPT.md / A3       规格文档（历史文件保留原样，不静默改写）
风格样稿/                 S3 静态原型（UI 基线）
spec/                     SPEC 的衍生工程制品（契约 / Fixture / 场景 / 验收矩阵）
progress/                 各模块独立进度与跨模块变更申请
tests/                    测试骨架（unit/contract/integration/e2e/security/performance）
```

- `spec/` 承载未来从 SPEC 生成的机器可读契约（`contracts/`）、测试数据与供应商 Fake（`fixtures/`）、E2E 场景（`scenarios/`）和验收矩阵（`acceptance/`）。
- `tests/` 按 SPEC §10 七层测试体系预留目录（Golden Set 数据存于 `spec/fixtures/golden-set/`），命名规范 `test_<requirement_id>_<behavior>()`。

## 开发纪律（详见 SPEC）

- **SDD 流程**：需求须达 `accepted` 才进入实现，未关联测试不得标记 `implemented`（SPEC §0.3）
- **TDD 流程**：Red → Contract → Green → Refactor → Integration → Regression（SPEC §0.4）；禁止"先写完整代码后补测试"
- **DoR / DoD**：见 SPEC §0.5
- **第一批 TDD 顺序**：安全边界与状态一致性 → 问答可信度 → 契约与体验 → 性能与灾备（SPEC §13.2）
- **外部 LLM/Embedding/Rerank**：单测必须用 Fake/Stub，供应商冒烟测试另行安排（SPEC §0.4）
- **契约落地**：`spec/contracts/` 中的 OpenAPI / JSON Schema 从 SPEC §5 与附录 B 生成，当前以 SPEC 为规范源（SPEC §5.1）
- **ADR**：改变状态机、权限、引用/删除语义、模型或检索配置时必须登记（SPEC §0.6、附录 E）

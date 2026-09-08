# 问枢 Pivot

企业私有文档检索问答（RAG）Web 系统。纯 Web 形态，MVP 固定 10 个页面，技术路线为 Next.js + FastAPI + PostgreSQL/MinIO/Qdrant/Redis + Celery（详见规格文档）。

> **当前状态：主线开发（MODULE-SPEC-1.1），Wave 3 进行中。** 工作区仅为本目录 `Pivot/` 的 `main`。领域服务与部分 HTTP 已在测试中挂载，但仍是 Fake/内存装配，**不能当作已上线系统**。下一刀见 [`PROGRESS.md`](PROGRESS.md)。
>
> 开发入口：先读 [`AGENTS.md`](AGENTS.md)，再读 [`MODULE_SPEC.md`](MODULE_SPEC.md) 和 [`PROGRESS.md`](PROGRESS.md)。**不要**为模块新建 `../Pivot-Mxx-*` worktree；历史副本禁止继续开发。

## 文档层级（规格优先级见 SPEC §0.1）

| 文件 | 定位 |
|---|---|
| `SPEC.md` | **规范源**（SPEC-1.0）：SDD + TDD 开发总规格，需求 → 场景 → 契约 → 数据 → 测试 → 验收 |
| `MODULE_SPEC.md` | **模块协作规范**（MODULE-SPEC-1.1）：边界、依赖、Owner、主线 Git、交接和集成门禁 |
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
MODULE_SPEC.md            模块协作规范（M00–M11、Wave、Owner、主线 Git）
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

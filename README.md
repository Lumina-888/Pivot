# 问枢 Pivot

企业私有文档检索问答（RAG）Web 系统。纯 Web 形态，MVP 固定 10 个页面，技术路线为 Next.js + FastAPI + PostgreSQL/MinIO/Qdrant/Redis + Celery（详见规格文档）。

> **当前状态：开发前规格基线（P0 预研前）。** 本仓库目前只包含规格文档、UI 静态原型与按 SPEC 附录 D 建立的工程骨架目录，**尚无真实后端、前端、数据库、部署或测试代码**。

## 文档层级（规格优先级见 SPEC §0.1）

| 文件 | 定位 |
|---|---|
| `SPEC.md` | **规范源**（SPEC-1.0）：SDD + TDD 开发总规格，需求 → 场景 → 契约 → 数据 → 测试 → 验收 |
| `技术方案GPT.md` | 工程实施增强基线（GPT-1.0） |
| `问枢Pivot-技术方案V2.md` | 产品范围与主要路线基线 |
| `问枢Pivot-A3门户设计.md` | 门户交互细节基线 |
| `风格样稿/` | S3 完整原型：UI 信息架构/视觉/交互回归基线，**Mock 行为不等于生产能力**（SPEC §1.5） |

`SPEC.md` 中的 `TBD-P0` 数值为未冻结参数，实现人员**不得私自替换为未记录的"默认值"**（SPEC 引言、§0.6）。

## 目录结构

```text
SPEC.md                  规范源（根目录，保持既有相对引用不动）
技术方案GPT.md / V2 / A3  规格文档（历史文件保留原样，不静默改写）
风格样稿/                 S3 静态原型（UI 基线）
spec/                     SPEC 的衍生工程制品（契约 / Fixture / 场景 / 验收矩阵）
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

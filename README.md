# 问枢 Pivot

问枢是面向企业知识库的智能问答系统。问答由 LangGraph 受控 ReAct 智能体执行：模型用只读工具搜索知识、读取证据，再根据观察决定下一步。权限、范围、外发、预算和答案发布全部由服务端控制。产品只有 Web 端。

## 架构概览

- **前端**：Next.js。
- **接口层**：FastAPI。运行状态经 SSE 推送，内部节点先投影为公开阶段再发布。
- **智能体**：LangGraph StateGraph，三个节点（decide、execute_tools、finalize）。工具白名单只有两个：`search_knowledge`（登记证据，只返回编号与计数）和 `read_evidence`（按编号读全文，每次重新授权）。最终答案只由收尾器根据已登记证据生成。
- **检索**：默认路径为 LlamaIndex 加 Qdrant。BM25 与稠密向量双路召回，RRF 融合，`BAAI/bge-reranker-v2-m3` 重排。嵌入使用硅基流动 `BAAI/bge-m3`。授权按文档与版本的实时事实复核。
- **数据与任务**：PostgreSQL、Redis、Celery、MinIO。
- **模型**：选型见 ADR-011。主模型是 DeepSeek 官方 `deepseek-flash`，备用是小米 `mimo-v2.6`，文档解析用 MinerU 官方云。
- **问答引擎**：`PIVOT_QA_ENGINE` 可切换。`pipeline` 是默认的确定性流水线，`agent` 走智能体。默认引擎待真实联调后决定。

## 当前状态

截至 2026-10-23，开发实现已全部合入 `main`（PR #2 至 #35）：

- **ND-AGENT-04**：持久化、加密检查点、版本锁、租约与 fencing、真实 PostgreSQL 故障矩阵。
- **LlamaIndex 集成 L1 至 L4**：默认检索路径已切换到 LlamaIndex，自研路径保留一个发布周期作回滚。
- **ND-AGENT-05**：模型全注入与主备切换、Agent Golden Set、真实模型 live 评测。
- **ND-GAP-01 至 04**：后台指标与任务列表真实接线、三套审计统一落库、改密强制标记、签名下载端点。
- **ND-P0-03**：真实嵌入与重排的检索全链 live 评测。
- **端到端各线**：网页上传入库（U1、U2）、Agent 生产接线（W1、W2）、检索相关性门禁与标定（线三，含稠密检索腿缺陷修复）、上下文瘦身（M 线）、答案层相关性判定。

GATE-P0 仍为 unverified。还剩三件不写代码的事项：

- **ND-P0-01-A**：企业集业务复核，进行中。复核完成后，评测用复核集重跑。
- **DR-010**：生产数值冻结。检索阈值、单 Run 调用上限等仍是 TBD-P0，候选值已由标定产出。
- **ND-STG-04-A**：staging 部署与低敏冒烟，待部署环境与信息。

实现事实、证据与已知差距的完整记录见 [PROGRESS.md](PROGRESS.md)。

## 当前规范

| 文件 | 定位 |
|---|---|
| [SPEC.md](SPEC.md) | 全局规范源 SPEC-1.1，覆盖需求、状态、HTTP、SSE、安全和验收 |
| [spec/AGENT_SPEC.md](spec/AGENT_SPEC.md) | Agent 专项 AGENT-SPEC-1.0，受 SPEC 管理 |
| [ADR-009](progress/changes/20261002-M00-langgraph-react-baseline.md) | 已接受的架构迁移，以及尚未关闭的决策 |
| [MODULE_SPEC.md](MODULE_SPEC.md) | MODULE-SPEC-1.2，覆盖模块责任、所有权和主线 Git |
| [AGENTS.md](AGENTS.md) | 新会话的启动与协作指令 |
| [PROGRESS.md](PROGRESS.md) | 实现事实、历史证据、已知差距和下一步 |
| [progress/next-dev-spec.md](progress/next-dev-spec.md)、[tickets.md](progress/tickets.md) | 开发计划和工单，不是需求源 |
| [spec/contracts/README.md](spec/contracts/README.md) | 公开契约 contract-v0.2；v0.1 信封仍然兼容 |

优先级以 SPEC 第 0.1 节为准。专项规格不能单独覆盖 SPEC。预算数值、框架版本、恢复字段和 checkpoint 治理，以对应 Contract 和 ADR 为准。

## 历史文档

技术方案 GPT、A3 门户设计和 `风格样稿/` 只保留历史参考。它们不决定当前 Agent 架构。SPEC-1.1 和 ADR-009 已经取代固定线性主图、自由多 Agent，以及 LangGraph 暂缓表述。

- [technical-plan-gpt.md](archive/technical-plan-gpt.md)（原技术方案GPT.md）是 GPT-1.0 的历史工程来源，不是当前实施总纲。
- `问枢Pivot-技术方案V2.md` 是未入库历史稿，已从工作区删除。路线以现行 SPEC 为准。
- [a3-portal-design.md](archive/a3-portal-design.md)（原问枢Pivot-A3门户设计.md）是历史页面和交互参考。
- `风格样稿/` 是 UI 回归基线。Mock 不等于生产能力。
- `.pi/artifacts/Pivot-LangGraph-ReAct改造方案.md` 已被专项规格取代，并已从工作区删除。以 `spec/AGENT_SPEC.md` 为准。

已入库的提交、tag、测试记录和验收证据都保留。旧的 implemented 记录不能改写成新的 FR-AGENT 已实现。

## 运行与测试

- 分组检查：`python ops/run_grouped_tests.py`。本地可用 `--skip-web` 跳过 web 组，CI 含 web 组与真实 PostgreSQL 组。
- 本地环境搭建见 [ops/runbook-local-linux.md](ops/runbook-local-linux.md)。
- 仓库内测试只用 Fake、Stub 或受控 Fixture。真实供应商验证走单独的 live 运行器（如 `ops/run_agent_live_eval.py`），密钥只从环境注入。

## 开发纪律

- SDD：需求 accepted 之后，先明确契约和数据影响，再实现。没有测试，就不能标 implemented。没有证据，就不能标 verified。
- TDD 顺序是 Red、Contract、Green、Refactor、Integration、Regression。测试命名为 `test_<requirement_id>_<behavior>()`。
- 模型和基础设施使用 Fake、Stub 或受控 Fixture。真实供应商冒烟单独运行。不得提交密钥或企业原文。
- 服务端注入用户和 scope。工具和恢复都要重新授权。校验前不发布正式事实。普通用户不看完整思考链。
- 不私设 `TBD-P0`。状态、权限、引用、删除、模型或检索配置发生变化时，登记 ADR。
- 收尾时更新模块进度和根进度，运行受影响测试，再按 MODULE_SPEC 提交。框架安装或旧测试绿灯，不能当作 ReAct 完成。

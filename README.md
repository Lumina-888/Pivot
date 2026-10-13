# 问枢 Pivot

问枢是面向企业知识库的 Web 系统。它使用 LangGraph 和受控 ReAct。模型用只读工具搜索知识、读取证据，再根据观察结果决定下一步。服务端控制权限、范围、外发、预算和答案发布。

技术路线包括 Next.js、FastAPI 和 LangGraph StateGraph，以及 PostgreSQL、MinIO、Qdrant、Redis 和 Celery。产品只有 Web。MVP 固定 10 个页面。

当前基线是 `17ac93a`。目标已经接受。主循环已有开发实现，验收尚未完成。已入库内容包括 LangGraph 工具循环、恢复契约 contract-v0.2、03-E 的 Web 恢复，以及 04-B 和 04-C 的持久化框架。跨进程恢复、04-D 至 04-F 和真实模型冒烟尚未完成。

Wave 3 夹具和单元测试不能代替 GATE。GATE-P0 全部 unverified。系统仍处于开发阶段。

工作区只使用 `E:/AI Project/Pivot` 的 `main`。不要新建 `../Pivot-Mxx-*` worktree。默认下一刀是 04-C 的后续，以及 04-D 至 04-F。详情见 [PROGRESS.md](PROGRESS.md)。

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

- [技术方案GPT.md](技术方案GPT.md) 是 GPT-1.0 的历史工程来源，不是当前实施总纲。
- `问枢Pivot-技术方案V2.md` 是未入库历史稿，已从工作区删除。路线以现行 SPEC 为准。
- [问枢Pivot-A3门户设计.md](问枢Pivot-A3门户设计.md) 是历史页面和交互参考。
- `风格样稿/` 是 UI 回归基线。Mock 不等于生产能力。
- `.pi/artifacts/Pivot-LangGraph-ReAct改造方案.md` 已被专项规格取代，并已从工作区删除。以 `spec/AGENT_SPEC.md` 为准。

已入库的提交、tag、测试记录和验收证据都保留。旧的 implemented 记录不能改写成新的 FR-AGENT 已实现。

## 开发顺序

1. ND-AGENT-01 已完成。它修复了迁移基线的答案安全问题。证据见 [nd-agent-01.md](evidence/agent-m05/nd-agent-01.md)。这不代表完整 Agent 已验收。
2. ND-AGENT-02 的内部契约已发布，D 至 H 已有开发实现。它覆盖内部 Contract 和 StateGraph 工具循环。生产运行尚未批准。
3. ND-AGENT-03 的 03-A 已发布 contract-v0.2，B、C、D、E 已有开发实现。它覆盖 Run、SSE、取消、澄清恢复和 Web。
4. ND-AGENT-04 的 04-A 已发布，04-B 和 04-C 的框架已提交。Claims、Citation、PostgreSQL checkpoint、执行租约和重启恢复尚未完成。
5. ND-AGENT-05 仍为 blocked。它覆盖受控真实模型冒烟和 Agent Golden Set。

DR-010 的生产数值尚未关闭。开发实现不等于运行批准。需求 accepted 之后，仍要满足 DoR 才能开工。

## 开发纪律

- SDD：需求 accepted 之后，先明确契约和数据影响，再实现。没有测试，就不能标 implemented。没有证据，就不能标 verified。
- TDD 顺序是 Red、Contract、Green、Refactor、Integration、Regression。测试命名为 `test_<requirement_id>_<behavior>()`。
- 模型和基础设施使用 Fake、Stub 或受控 Fixture。真实供应商冒烟单独运行。不得提交密钥或企业原文。
- 服务端注入用户和 scope。工具和恢复都要重新授权。校验前不发布正式事实。普通用户不看完整思考链。
- 不私设 `TBD-P0`。状态、权限、引用、删除、模型或检索配置发生变化时，登记 ADR。
- 收尾时更新模块进度和根进度，运行受影响测试，再按 MODULE_SPEC 提交。框架安装或旧测试绿灯，不能当作 ReAct 完成。

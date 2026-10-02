# 问枢 Pivot

面向企业知识库的 **LangGraph + 受控 ReAct AI Agent** Web 系统。模型通过只读工具选择搜索与证据读取，根据 Observation 再次决策；服务端强制控制权限、scope、外发、预算及答案发布。

技术路线：Next.js + FastAPI + LangGraph StateGraph + PostgreSQL/MinIO/Qdrant/Redis + Celery 文档处理。纯 Web，MVP 固定 10 个页面。

> **目标已接受，Agent 尚未实现。** 当前代码仍为纯 Python 线性 RAG；框架/工具循环/checkpoint 待改造，已发现的答案门禁漏洞待修复。Wave 3 夹具与历史测试不等于新 Agent 验收；GATE-P0 全部 unverified，不是已上线系统。
>
> 工作区仅为 `E:/AI Project/Pivot` 的 `main`，不要新建 `../Pivot-Mxx-*` worktree。默认下一刀是 **ND-AGENT-01：答案安全 Red 回归与修复**，详见 [PROGRESS.md](PROGRESS.md)。

## 当前规范

| 文件 | 定位 |
|---|---|
| [SPEC.md](SPEC.md) | **全局规范源 SPEC-1.1**：需求、状态、HTTP/SSE、安全和验收 |
| [spec/AGENT_SPEC.md](spec/AGENT_SPEC.md) | **Agent 专项 AGENT-SPEC-1.0**：受 SPEC 管理，FR-AGENT-001~010、工具/循环/预算/恢复/答案发布 |
| [ADR-009](progress/changes/20261002-M00-langgraph-react-baseline.md) | 已接受的架构迁移、旧文档取代记录及未关闭决策 |
| [MODULE_SPEC.md](MODULE_SPEC.md) | MODULE-SPEC-1.2：模块责任、所有权、主线 Git 与交接 |
| [AGENTS.md](AGENTS.md) | 新会话启动与协作指令 |
| [PROGRESS.md](PROGRESS.md) | 实现事实、历史证据、已知差距与下一步 |
| [progress/next-dev-spec.md](progress/next-dev-spec.md)、[tickets.md](progress/tickets.md) | Agent 关键路径与旧 Wave 3/STG/P0 工单，不是需求源 |
| [spec/contracts/README.md](spec/contracts/README.md) | 已发布兼容契约 contract-v0.1；新恢复接口尚未冻结/发布 |

优先级以 SPEC §0.1 为准。专项规格不是第二份可独立覆盖 SPEC 的总规格；预算数值、框架版本、恢复字段和 checkpoint 治理仍需对应 Contract/ADR。

## 历史文档

技术方案 GPT、V2、A3 与 `风格样稿/` 仅保留历史工程、产品或交互参考，不再独立决定 Agent 架构。固定线性主图、自由多 Agent 和 LangGraph 暂缓表述已由 SPEC-1.1/ADR-009 取代。

- [技术方案GPT.md](技术方案GPT.md)：GPT-1.0 历史工程来源，不是当前实施总纲。
- `问枢Pivot-技术方案V2.md`：当前工作区存在的用户未跟踪历史文件，保留不删除；其路线不得覆盖当前 SPEC。
- [问枢Pivot-A3门户设计.md](问枢Pivot-A3门户设计.md)：历史页面/交互参考。
- `风格样稿/`：UI 回归基线，Mock 不等于生产能力。
- `.pi/artifacts/Pivot-LangGraph-ReAct改造方案.md`：已被专项规格取代的讨论稿。

不删除提交、tag、测试记录或验收证据，不将旧 implemented 记录改成新 FR-AGENT 已实现。

## 开发顺序

1. ND-AGENT-01：修复自由 Markdown 与已验证 Claims 不一致的答案发布路径。
2. ND-AGENT-02：冻结模型/工具/预算内部 Contract，接入真实 StateGraph + Fake tool-calling model。
3. ND-AGENT-03：Run/SSE、取消、澄清恢复与 Web；先冻结新增公开契约。
4. ND-AGENT-04：Claims/Citation、Postgres checkpoint、执行租约、事件一致性与重启恢复。
5. ND-AGENT-05：受控真实模型能力冒烟及 Agent Golden Set。

后续切片在预算、接口或持久化前置条件不足时 blocked，不因需求 accepted 跳过 DoR。

## 开发纪律

- SDD：需求 accepted、契约/数据影响明确后再实现；无测试不得 implemented，无证据不得 verified。
- TDD：Red → Contract → Green → Refactor → Integration → Regression；命名 `test_<requirement_id>_<behavior>()`。
- 模型和基础设施使用 Fake/Stub 或受控 Fixture；真实供应商冒烟单独运行，不提交密钥或企业原文。
- 服务端注入用户/scope；工具和恢复重新授权；校验前不发布正式事实，普通用户不看完整思考链。
- 不私设 `TBD-P0`；状态、权限、引用/删除、模型或检索配置变化登记 ADR。
- 收尾更新模块/根进度，运行受影响测试，按 MODULE_SPEC 提交；不把框架安装或旧测试绿灯当 ReAct 完成。

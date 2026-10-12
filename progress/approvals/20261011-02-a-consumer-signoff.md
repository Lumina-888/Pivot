# 02-A 消费者签认记录

| 字段 | 记录 |
|---|---|
| 记录 ID | CONSUMER-02-A-20261011 |
| 签认人 / 角色 | lumina888 / 项目 Owner 兼任全部消费者角色（M00/M01/M03/M04/M05/M06/M11） |
| 可追溯确认 | 用户明确回复"同意" |
| 记录时间 | 2026-10-11 |
| 审批对象 | AGENT-INTERNAL-0.1-draft.1 及 PR-01 用户输入 Prompt 重写补充 |
| 输入 commit | `32dd4e739326497a8e5358d102a9a71dd5bc1afc` |
| 前置依据 | Owner 设计批准（OWNER-02-A-20261006）；Phase 0-3 技术验证通过（eef40df） |
| 结论 / 生效范围 | 同意；消费者签认完成，可进入契约发布准备；不批准生产启用或 GATE 放行 |

## 签认内容

### M00（契约治理）
- ✅ Interface 定义清晰：AgentModel.decide/capabilities、ToolExecutor.execute、StructuredFinalizer.finalize、EvidenceResolver.resolve、ResultPublisher.publish
- ✅ 版本化管理：提案版本 AGENT-INTERNAL-0.1-draft.1，输入 commit 32dd4e7，配置追踪包含 index_generation/embedding_model_version/retrieval_config_version
- ✅ 不进入 contract-v0.1 manifest（仅适用于新 Agent）

### M01（身份授权）
- ✅ 每次调用都经过：可信身份/owner/scope 与取消检查 → 最新文档和外发策略检查
- ✅ principal/scope 边界明确，不从用户数据（原始输入或重写结果）提升权限
- ✅ 工具 schema 仅为 query 或 evidence_id，拒绝 principal/scope/URL/路径/SQL
- ✅ PR-01 重写不改变服务端身份、owner、scope、文档资格、外发策略和工具白名单

### M03（数据基础）
- ✅ EvidenceRegistry 去重：按 (document_id, version_id, chunk_id, index_generation) 在本 Run 内去重
- ✅ 版本追踪：version_label、生效区间与冲突关联来自事实源，不从模型文本推断
- ✅ 相同身份内容 hash 或真实定位不一致是事实一致性错误，不覆盖
- ✅ 注册前由服务端从 M04 结果与 M03 事实源补齐/核实资格和定位

### M04（检索 RAG）
- ✅ 工具 schema 与检索接口兼容：search_knowledge 接收 query，返回 evidence_id/excerpt/locator/版本元数据
- ✅ read_evidence 接收 evidence_id，返回 text 和完整元数据
- ✅ 合法观察作为不可信 ToolMessage.content JSON 数据，不提升为 system/developer 指令
- ✅ 版本/权限/外发改变后旧 Observation 必须作废

### M05（ReAct/QA）
- ✅ 单工具/控制意图协议可实现：每回合恰好一个工具调用，或一个完整 JSON 控制意图
- ✅ 技术验证完成：Phase 0-3 测试通过（eef40df），4 个 e2e 测试覆盖 search/read/structured-answer/budget-gate
- ✅ PR-01 可实现：InputRewriter.rewrite 接收原始用户输入及授权上下文，返回非空重写请求和版本引用
- ✅ 输入重写与检索 query rewrite 分开追踪，query rewrite 最多 2 次、澄清最多 1 轮不变

### M06（导出/审计）
- ✅ 调用 ID 追踪：message_id/step_id/attempt_id 由服务端稳定分配，与供应商 tool_call_id 分开
- ✅ 用量追踪：实际用量或明确 unknown 用量，unknown 不记零
- ✅ 来源追踪：稳定 action_id/step_id、原 tool_call_id、来源工具、授权检查时点
- ✅ 数据策略快照：classification/external_llm_allowed 等资格快照及检查时点按敏感状态白名单关联保存

### M11（集成/质量）
- ✅ 已有技术验证覆盖核心路径：
  - ScriptedModel 模拟多轮工具调用和控制意图
  - CorpusRetriever 模拟检索结果
  - EchoWriter 模拟结构化输出
  - 4 个测试用例：单次搜索、多轮检索、结构化答案、预算耗尽
- ✅ 测试通过：4 passed in 5.39s（commit eef40df）
- ✅ Ruff check/format 通过，LSP 诊断 0 错误

### Owner（实施范围）
- ✅ 仅适用于新 Agent，不进入 contract-v0.1 manifest，不影响现有 QA 端口
- ✅ 不修改 api/、worker/、web/、依赖、迁移或公共 schema
- ✅ 不安装 LangGraph、不添加恢复 endpoint、不改变 HTTP/SSE 状态或错误枚举

## 未批准及待完成事项

本次签认完成消费者审核，但以下事项仍 pending：
- 02-B BUDGET draft.3 签认
- 02-C DEPENDENCIES draft.1 签认
- PR-01 的具体 schema 与三组运行时 Red 测试实现
- 契约发布（M00）
- 03-A 恢复、04-A 持久化签认
- staging/生产启用
- GATE 放行

因此 02-A 状态更新为 **approved**（Owner + 消费者签认完成），但全局仍需推进 02-B/C 及后续工单。

## 依据

- [批准版本对应的 02-A 提案](../changes/20261002-M05-agent-internal-contract.md)
- [Owner 设计批准记录](20261006-02-a-owner-design.md)（OWNER-02-A-20261006）
- [Phase 0-3 技术验证](../../tests/e2e/test_agent_complete_flow.py)（commit eef40df）
- [技术证据与审批入口](../../evidence/agent-m03/nd-agent-02-abc-review.md)

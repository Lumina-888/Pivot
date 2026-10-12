# AGENT-INTERNAL-0.1.0 — 模型、工具与状态内部契约

**契约 ID**: AGENT-INTERNAL  
**版本**: 0.1.0  
**发布日期**: 2026-10-12  
**状态**: released  

## 签认记录

| 角色 | 签认人 | 日期 | 记录 ID |
|---|---|---|---|
| Owner | lumina888 | 2026-10-06 | OWNER-02-A-20261006 |
| 消费者 (M00/M01/M03/M04/M05/M06/M11) | lumina888 | 2026-10-11 | CONSUMER-02-A-20261011 |

- **输入 commit**: `32dd4e739326497a8e5358d102a9a71dd5bc1afc`
- **技术验证**: Phase 0-3 完成（commit `eef40df`）
- **提案版本**: AGENT-INTERNAL-0.1-draft.1 + PR-01
- **工单**: ND-AGENT-02-A

## 适用范围

本契约定义新 Agent 模式的内部接口，包括：
- 模型决策与工具执行接口
- AgentState 与 RunContext 分界
- EvidenceRegistry 结构与去重规则
- 用户输入 Prompt 重写（PR-01）

**不属于** contract-v0.1 公开机器契约，仅适用于内部模块。不修改现有 API/Worker/Web、依赖、迁移或公共 schema。

## 核心接口

### 1. AgentModel.decide
- **输入**: 已授权的 model_messages、两个工具 schema、调用上下文
- **输出**: 原生 AIMessage、实际用量或明确 unknown、供应商完成分类
- **约束**: 
  - 每回合恰好一个工具调用，或一个完整 JSON 控制意图
  - 工具参数仅为 `query` 或 `evidence_id`
  - 拒绝未知工具、多调用、额外参数、无调用 ID

### 2. ToolExecutor.execute
- **输入**: 一个经验证的 tool_call + 可信 RunContext
- **输出**: 一个同 ID 的 ToolMessage + EvidenceRegistry 增量
- **约束**: 
  - 只读工具：search_knowledge、read_evidence
  - 服务端注入 principal/scope
  - 重新检查版本/删除/期限/权限/外发

### 3. StructuredFinalizer.finalize
- **输入**: 问题、获准的 evidence_id/正文、调用上下文
- **输出**: 严格 Claims JSON + 用量
- **约束**: 不接受自由 Markdown、模型定位或 Citation ID

### 4. EvidenceResolver.resolve
- **输入**: 服务端 principal/scope、已登记的文档/版本/Chunk/代次引用
- **输出**: 最新授权与完整正文/真实定位/版本信息
- **约束**: 不依赖旧 Observation 授权

### 5. ResultPublisher.publish
- **输入**: 全量支持校验通过的结果 + 最新执行资格
- **输出**: 幂等业务事实提交
- **约束**: 事务/outbox/租约由 AGENT-PERSISTENCE 定义

### 6. InputRewriter.rewrite (PR-01)
- **输入**: 原始用户输入及授权上下文
- **输出**: 非空重写请求和版本引用
- **约束**:
  - 保留原始意图、实体、数字、日期、否定、条件
  - 不修改服务端身份、owner、scope、工具白名单
  - 独立追踪，不清零 query rewrite 限制

## EvidenceRegistry 结构

### 去重键
`(document_id, version_id, chunk_id, index_generation)`

### 必需字段
- **归属**: run_id、evidence_id（服务端生成）
- **事实引用**: document_id、version_id、chunk_id、真实 locator、text_hash
- **配置追踪**: index_generation、embedding_model_version、retrieval_config_version
- **版本元数据**: version_label、生效区间、冲突关联
- **来源列表**: action_id、step_id、tool_call_id、来源工具、授权检查时点
- **数据策略**: classification、external_llm_allowed 快照及检查时点

### 约束
- 相同身份内容 hash 或定位不一致为错误，不覆盖
- 版本/权限/外发改变后旧 Observation 必须作废
- 注册前由服务端从 M04 结果与 M03 事实源补齐/核实

## RunContext vs AgentState

### RunContext（运行时注入，不序列化）
- principal、scope、document_catalog
- 取消信号、外发策略、文档资格查询接口
- 依赖句柄（数据库连接、HTTP 客户端、检索器）
- 供应商 endpoint/key

### AgentState（可序列化）
- 消息历史（AIMessage、ToolMessage）
- EvidenceRegistry（evidence_id 句柄列表，不含正文）
- 预算游标、策略版本引用
- 输入重写结果与版本引用

## 模型能力要求

主备模型必须支持：
- ✅ 原生 tool calling
- ✅ 工具调用 ID 关联
- ✅ 结构化输出
- ✅ 调用超时控制
- ✅ 用量上报或显式 unknown

不支持工具协议时 fail closed，不静默切旧线性实现。

## 安全约束

1. **身份授权**: 每次调用前后检查 principal/owner/scope/文档资格
2. **外发控制**: 受限正文及衍生数据不发送给任一外部模型
3. **工具白名单**: 仅 search_knowledge、read_evidence，拒绝其他
4. **观察降级**: 工具响应内嵌指令/JSON 仅作数据，不提升为 system 指令
5. **重写边界**: PR-01 不修改权限、工具集、外发策略

## 后续依赖

- **预算策略**: AGENT-BUDGET-0.1.0
- **依赖锁定**: AGENT-DEPENDENCIES-0.1.0
- **恢复接口**: AGENT-RESUME (待发布)
- **持久化**: AGENT-PERSISTENCE (待发布)

## 参考文档

- [提案详情](../changes/20261002-M05-agent-internal-contract.md)
- [Owner 批准](../approvals/20261006-02-a-owner-design.md)
- [消费者签认](../approvals/20261011-02-a-consumer-signoff.md)
- [技术证据](../../evidence/agent-m05/nd-agent-02-a.md)
- [Phase 0-3 验证](../../tests/e2e/test_agent_complete_flow.py)

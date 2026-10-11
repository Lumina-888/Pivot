# ADR-010：Phase 1 LlamaIndex 检索适配（本机开发）

- 状态：accepted（本机开发与合成夹具）；依据 Owner 已填写确认单及本轮“Phase 1: LlamaIndex 检索集成”实施指令。
- Accountable：M04；Contributors：M03 依赖，M05 工具消费者，M11 脚本/集成测试。
- 基线：main `06c9417`；最新交接 `.pi/handoffs/20261011-agent-implementation-session.md`。根 HANDOFF/PROGRESS 的 10 月 6 日记录保留为历史。
- 需求：FR-RAG-001/002/003/004/006、FR-RBAC-003、FR-AGENT-002；公共契约保持 contract-v0.1。

## 决策与边界

LlamaIndex 管向量索引与 dense 召回，LangGraph 管流程。适配器实现既有 `qa.ports.Retriever.retrieve`，复用 M04 BM25/RRF/过滤和单路降级。只调用检索接口，不创建 QueryEngine，不调用答案模型。

依赖以 optional extra `llama-index` 固定 `llama-index-core==0.11.23`（交接的 0.11.x 具体版本），本机安装验证。Embedding 必须显式注入；复用既有 QueryEmbedder 的桥接适配，避免引入默认 OpenAI 配置。持久化 demo 使用 LlamaIndex SimpleVectorStore；Qdrant 生产发布/Worker 索引迁移不在本刀。

参数、tokenizer、dense 相关性阈值与资源授权回调显式注入。top-5 仅用于合成 demo，不冻结生产 TBD-P0。缺资源身份、真实定位、代次/Embedding/检索版本或状态元数据的节点不作为证据；严格过滤 ready/current/未删/未过期和结构化 scope。principal 授权回调每次请求执行，不靠索引元数据授予身份权限；外发许可必须保留原值，不默认 true。

本机 fixture 的授权目录与文档索引是合成数据，只允许 demo 用户；上线需注入最新业务事实源授权，不把持久化索引当权限事实源。

## 契约与验收

- 输入：非空 question/principal；scope 为 global 或 document（document 必填 ID）。无效输入返回 failed/RESOURCE_FORBIDDEN，零证据。
- 输出：found/empty/failed + EvidenceHit，真实 chunk/document/version/text/locator/external_llm_allowed；不伪造 unknown/v1 或 score locator。
- 检索失败脱敏，单路失败由既有混合服务降级；全部失败无证据。
- 测试边界沿交接路线图：Retriever 公共协议、索引构建/加载、SearchKnowledgeTool/ToolExecutor 消费。真实 LlamaIndex + 可控 Embedding，禁止测试时收费 API。
- Red → Green 覆盖证据转换、scope/状态/权限负向、空检索、持久化加载及工具读证据；相关既有 QA/检索回归。
- 3 个 500–1000 字合成制度文档，脚本输出 tests/fixtures/index（生成物忽略）。

Phase 2 才接真实 decide 模型；本刀工具集成不代表完整自主 ReAct、持久恢复或 GATE-P0 通过。

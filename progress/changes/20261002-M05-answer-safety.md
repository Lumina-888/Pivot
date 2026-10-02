# ND-AGENT-01：答案安全门禁实施 Contract

- **日期 / 状态**：2026-10-02 / accepted（Owner 指定 ND-AGENT-01；细化已接受 ADR-009，不新增需求语义）。
- **Accountable**：M05；M00 契约记录、M04 transport 失败分类、M11 回归/证据贡献。
- **依据**：SPEC-1.1 FR-QA-002/004、AGENT-SPEC-1.0 §7、ADR-009。
- **原契约**：公开 contract-v0.1 不变；旧 HTTP Writer 允许自由 Markdown fallback，CandidateVerifier 只检查候选 Chunk 集合。

## 范围与回归边界

按 Owner 所选工单已登记的边界，通过真实 QaOrchestrator + RunService/EventLog 复现问题；仅外部模型 HTTP transport 与检索基础设施使用 Fake。回归覆盖 HTTP Run/SSE/会话消息与既有导出路径，不使用私有方法验证答案安全。

- 首个 Red：考勤证据 + 无关奖金 Markdown 不得 answered。
- 后续逐项 Red：非法 JSON/Claims、候选外/悬空引用、反向绑定/版本/locator 错误、数字/日期/条件/否定/版本差异、Verifier 故障或非法输出、SSE 校验前泄漏。
- 不安装 LangGraph、不新增公开路由/枚举/错误码、不冻结 DR-004/010/011 或其他 TBD-P0。

## 输入、输出与失败策略

- HTTP Finalizer 接受严格 JSON 对象：`{"claims":[{"text":"事实","evidence_index":0}]}`。索引为本次请求的服务端候选序号，必须是非 bool 整数且在范围内。
- 兼容旧 JSON 的可选字符串 `markdown` 字段，但其内容永不成为发布事实；额外字段、非法成员、空 Claims、无效索引整份拒绝。不接受自由 Markdown/代码围栏，不跳过非法 Claim，不从证据补造 Claims 背书原文。
- Citation/Claim ID 及 document/version/chunk/locator 由服务端生成，每个绑定完整且唯一；Verifier 接收真实 EvidenceHit 元组，而非只有 Chunk ID 的集合。
- 首版默认支持检查采取保守的逐字证据策略：Claim 必须等于所引用 Chunk 的完整正文（仅忽略首尾空白），不接受截取条件/否定/版本限定后的片段。未知改写返回 uncertain，而非以词语/数字相似度猜测支持。语义 Judge/阈值仍属 DR-004，未冻结。
- 任一 Claim 或绑定不通过，整份候选不发布。非法结构使用既有 `VERIFICATION_UNAVAILABLE`（不触发供应商故障 failover）；无有效发布结果时不保留草稿 Claims/Citation/答案或发送 token/citation。
- 最终文本只由已通过校验的 Claims 渲染；安全门禁独立于可注入辅助 Verifier，不允许其绕过结构/支持检查。
- HTTP 执行边界在结果提交后发布答案事件；跨进程事件 outbox、Claims/Citation 事务持久化仍由 ND-AGENT-04 承接，不能宣称 exactly-once。

## 影响与兼容

M05：`api/src/pivot/qa/**`、必要的 Run HTTP 提交/发布接线、QA 测试；RunBundle 注解纠正为实际使用的 dict 列表，不变更数据字段。M04：`retrieval/providers.py` 为非 JSON/非对象 HTTP 响应增加兼容的 JsonHttpError 子类，供 Writer 区分格式错误与网络故障；旧消费者仍可捕获基类，检索策略不变。M11：HTTP Writer 集成夹具与答案安全证据。M00：本记录、工单/矩阵/进度。历史正向 Fake 自由文本需改为真实证据支持的 JSON，不能保留旧漏洞作为兼容要求。公开 HTTP/SSE schema、数据库迁移与模型配置不变。

## ADR 与审核

引用/支持/发布策略执行 ADR-009 已批准的全量门禁，无新政策决策；不引入局部删句发布。实施检查与测试证据写入根 PROGRESS、M05/M00/M11 及 `.pi/artifacts/`。全部 GATE-P0 继续 unverified。

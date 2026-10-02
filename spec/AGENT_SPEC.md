# 问枢 Pivot — LangGraph ReAct Agent 专项规格

| 项目 | 内容 |
|---|---|
| 文档 ID / 版本 | AGENT-SPEC-1.0 |
| 日期 / 状态 | 2026-10-02 / accepted（目标与安全不变量；未实现、未验收） |
| 上位规范 | [SPEC.md](../SPEC.md) SPEC-1.1 |
| 决策记录 | [ADR-009](../progress/changes/20261002-M00-langgraph-react-baseline.md) |
| Accountable | M05；公共契约 M00、持久化 M03、安全 M01、验收 M11 |
| 实现现状 | 纯 Python 线性 RAG；LangGraph、ReAct、工具调用和 checkpoint 尚未接入 |

## 0. 规范地位与实施边界

本文是 SPEC §7 引用的 Agent 专项规范，不是第二份独立总规格。SPEC 管理全局需求、公开状态和 HTTP/SSE；本文细化 FR-AGENT-* 的内部模型、工具、执行与验收。冲突时以 SPEC 和其登记 ADR 为准。

已取代旧“固定线性主图”和“LangGraph 可无限期暂缓”的目标；没有改写旧提交的实现事实。历史线性实现仅可作为受安全修复保护的短期回归基线，不能作为新 Agent 需求的验收证据。

公共恢复接口、新错误映射、框架版本、预算数值、checkpoint 保留/加密策略仍待各自 Contract/ADR。相关事项阻断其依赖切片，不阻断先编写答案安全回归测试和 Fake ReAct 图测试。所有 `TBD-P0` 保持未冻结。

## 1. 产品目标与非目标

构建企业知识库内的受控 ReAct AI Agent：模型选择允许的工具及查询，根据工具 Observation 决定下一步，直到得到可验证答案、澄清请求或明确拒答/失败。

- 必须真实使用 LangGraph StateGraph、条件路由及消息状态；将旧线性函数包装成图不满足要求。
- 必须使用原生 tool calling，正确关联 AIMessage.tool_calls、工具调用 ID 和 ToolMessage；不靠正则解析自由文本 Thought/Action。
- 模型控制行动顺序，服务端控制身份、权限、scope、预算、外发、取消及答案发布。
- 保留已有混合检索、文档处理、存储、鉴权和十页产品范围。
- 首版只读，不开放任意网络、Shell、代码执行、SQL、删除、上传、用户管理和导出工具；原有显式 HTTP 操作继续保留。
- 不采用自由群聊式多 Agent，不将完整思考链作为产品输出。

## 2. 需求登记与追踪

下表需求均为 P0、阶段 P0/P1、状态 accepted；没有对应实现或验收证据，不得标 implemented/verified。用户价值是可执行、可信、受权限与成本约束的自主知识库问答。

| ID | 标题 / Accountable | 场景 | 契约与数据 | 首批测试 ID | 证据 / 依赖 |
|---|---|---|---|---|---|
| FR-AGENT-001 | 真实 LangGraph ReAct 循环 / M05 | 工具观察改变下一步选择 | §3 图、消息状态 | test_FR_AGENT_001_observation_drives_next_tool | 图执行与工具轨迹；模型工具接口 |
| FR-AGENT-002 | 白名单只读工具 / M05 | 搜索后选择读取证据 | §4 工具、EvidenceRegistry | test_FR_AGENT_002_read_only_tools | 参数/路由测试；M04 检索 |
| FR-AGENT-003 | 可信上下文与外发门禁 / M01 | 伪造身份/scope 或受限证据 | §4~5 上下文、文档策略 | test_FR_AGENT_003_model_cannot_expand_scope | 安全负向报告；FR-RBAC/FR-RAG |
| FR-AGENT-004 | 有界执行与累计预算 / M05 | 重复调用、重写、供应商切换 | §6 Budget、ProviderCall | test_FR_AGENT_004_budget_survives_resume | 用量与终止测试；DR-010 |
| FR-AGENT-005 | 从验证事实发布答案 / M05 | 模型 Markdown 与证据不一致 | §7 Claims/Citation/Message | test_FR_AGENT_005_unverified_markdown_never_published | F3 负向回归；FR-QA-002/004 |
| FR-AGENT-006 | checkpoint 与单执行者 / M03 | 节点后崩溃、并发认领 | §8 checkpoint、租约、attempt | test_FR_AGENT_006_restart_from_checkpoint | PostgreSQL 重启/竞争证据；DR-011 |
| FR-AGENT-007 | 有界澄清与授权恢复 / M05 | interrupt 后用户回复 | §8、FR-QA-006；恢复契约待冻结 | test_FR_AGENT_007_resume_is_owner_isolated | 恢复/重复请求测试；M00 恢复契约 |
| FR-AGENT-008 | 安全公开轨迹与取消 / M05 | SSE 重连、取消、晚到结果 | §9、既有 SSE 信封 | test_FR_AGENT_008_cancel_blocks_late_answer | SSE/取消竞态报告；FR-STREAM |
| FR-AGENT-009 | 模型能力与版本可追溯 / M11 | 不支持 tools 或备用模型切换 | §10 模型适配、版本、用量 | test_FR_AGENT_009_tool_capability_required | 锁版本及受控 live 冒烟；DR-001/007 |
| FR-AGENT-010 | Agent 质量与安全回归 / M11 | 不同观察、注入、空证据 | §11 Agent Golden Set | test_FR_AGENT_010_golden_set_agent_paths | Fake 与 live 分开的报告；业务复核 |

每个场景的 Given/When/Then 与异常边界见下文及 [qa.feature](scenarios/qa.feature)。验收矩阵见 [matrix.md](acceptance/matrix.md)，工单见 [tickets.md](../progress/tickets.md)。ND-AGENT-01 已新增 FR-AGENT-005 安全回归（[证据](../evidence/agent-m05/nd-agent-01.md)）；完整事实事务/outbox 未验收，其他 Agent 测试名称仍为登记计划。

## 3. 图与模型控制契约

```text
START → input_guard → load_context → agent
agent --tool_calls--> tool_guard → tools → observation_guard → agent
agent --clarify--> clarify / interrupt → authorized_resume → agent
agent --finalize--> build_evidence → structured_finalize → verify
verify --supported--> persist_result → END
verify --need_more_evidence且有预算--> repair_feedback → agent
verify --unsupported/uncertain且不可补证--> refuse_or_uncertain → persist_result → END
```

所有模型与工具调用前检查预算、取消、身份及外发策略；返回后再次检查取消和最新资源资格。

- Given 首次检索不足；When 模型收到合法 Observation；Then 它可以在预算内改写查询、选择 read_evidence、准备回答或结束。代码不得固定“总是搜索两次”冒充自主决策。
- Given 模型提出 tool_calls；Then 工具只能经 tool_guard 后执行，结果按原 tool_call_id 回传。
- Given 无工具调用且模型提出结束；Then 只接受内部控制意图 finalize/clarify/refuse，不能直接发布自由文本。finalize 必须进入独立结构化 Finalizer 和 Verifier。
- 首版一次模型响应最多执行一个工具调用；多调用输出视为协议不符合，不能隐式并行。具体公开错误映射在模型 Contract 冻结；循环不得因此重置预算。
- 工具错误只返回脱敏分类；取消、权限或外发禁止立即停止相关路径，不允许切换工具/供应商绕过。
- 失败格式不是供应商临时故障，不做基础设施自动重试。合法的证据不足 Observation 可触发有限新行动，区别于重试相同失败调用。

LangGraph 调度错误或协议非法不得默认为 answered。ToolNode 可作内部执行适配，但必须满足上述串行和安全门禁；图内部消息不直接暴露 HTTP。

## 4. 工具白名单与证据

| 工具 | 模型参数（严格 schema，拒绝额外字段） | 服务端行为 | 返回 Observation |
|---|---|---|---|
| search_knowledge | query：非空字符串 | 注入 principal/scope；调用现有混合检索；执行预算、状态/权限/外发过滤 | status、opaque evidence_id、限长摘要及许可元数据 |
| read_evidence | evidence_id：非空字符串 | 仅解析本 Run 已登记合法候选；重新授权、检查删除/期限/版本/外发资格 | status、限长正文、真实 locator 和版本信息 |

不得将 principal_id、scope、任意 URL、存储路径、检索配置、模型/密钥或 SQL 作为模型可填写参数。

EvidenceRegistry 是服务端维护的映射：evidence_id → document_id/version_id/chunk_id/locator/index_generation/检索与 Embedding 版本/来源动作。记录工具调用 ID 和授权时点，以便审计和最终重新校验。

同一 Run 多次检索去重，但保留来源；不得将不同文档版本混成一个证据对象。历史引用不得直接成为新 Run 候选，必须重新解析、授权和登记。查询涉及版本冲突时保留允许展示的冲突信息，不由模型静默裁决。

Given 模型猜测另一个 Run 的 evidence_id；When 调用 read_evidence；Then 不返回正文或泄露存在性。Given 文档已删除、过期或权限改变；Then 不沿用旧 Observation 作为有效答案依据。

## 5. 状态、上下文与外发

### 5.1 可信 RunContext

服务端注入 run_id、conversation_id、principal、有效 scope、依赖句柄、供应商策略、预算策略和取消句柄。它们不是模型生成的权限依据，也不是可由任意客户端传入的 thread_id。

### 5.2 可序列化 AgentState

包含执行所需的 messages、合法 Observation、EvidenceRegistry、pending tool calls、稳定 step/attempt 标识、预算/用量、rewrite_count、clarification_count、结构化草稿和校验结果。

- 框架消息、ToolMessage 与工具 ID 的对应关系必须可以恢复。
- API key、连接对象、系统凭证与供应商私有 reasoning 字段不得进入 checkpoint、公开轨迹或普通日志。
- 内部消息和证据是敏感执行数据；checkpoint 的访问、保留、删除、加密与备份经 DR-011 冻结，不视为可公开的“调试日志”。
- 恢复时重新构造可信上下文，验证用户 active、会话 owner、scope 及文档资格；存储中的旧上下文不能授权已失效资源。

### 5.3 每次模型调用都执行外发门禁

检查 Planner、Finalizer、Verifier、备用供应商调用，以及会话历史、检索摘要和工具 Observation。不得仅在最终草稿写作前检查 external_llm_allowed。

Given 某文档禁止外发；When 搜索或读取后准备调用外部模型；Then 其正文、摘要、衍生历史及受保护元数据不得发送。无合法数据路径时按 FR-QA-003 结束；不自动切换外部供应商。

会话历史从业务 Message 加载经过授权的必要窗口/摘要，窗口和摘要预算仍为 TBD-P0。文档文本是数据而非指令；Prompt Injection 不改变工具白名单或权限。

## 6. 预算与终止

- query rewrite 最多 2 次；每 Run 最多 1 轮澄清，沿用 SPEC 已冻结约束。
- 初次 search_knowledge 不计 rewrite；首次之后 query 改变的搜索计一次 rewrite；重复相同 query 仍计工具/模型调用预算，不能形成无限循环。
- 最大模型/工具调用数、总/单步超时、token/费用、观察长度、并发与 recursion_limit 数值为 TBD-P0，登记 DR-010。单元测试可明确注入有限 Fixture 值，不成为生产默认。
- recursion_limit 是图 super-step 上限，不替代工具、模型、token 与费用预算。
- checkpoint 保存已消费预算；恢复、重试、备用模型及检索补证均共享同一 Run 剩余预算。
- 所有调用前检查剩余额度，返回后登记实际用量。额度耗尽不得发布未验证答案。
- 已有且通过校验的事实可以按批准发布策略完成；没有可用证据时 refused，支持性仍不确定时 uncertain，执行故障按 SPEC 错误语义 failed。
- 禁止通过无效格式或错误协议自动重试修绿；只有 SPEC 允许的超时/429/临时 5xx/网络故障可走基础设施重试。

Agent 运行模式缺必需预算配置必须 fail closed；依赖预算的实施切片在 DR-010/Contract 未满足前 blocked。

## 7. 结构化答案与发布

与 FR-QA-002/004 共用以下硬门禁，旧模式也必须遵守。

1. Finalizer 输出事实性 Claims（text + 本 Run evidence_ids）；不将自由 Markdown 当可信结果。
2. 格式非法、无合法 Claims 或候选引用非法时，不得用证据 Claims 给另一段自由文本背书；不得静默生成替代 Claims 后保留原 Markdown。
3. 服务端生成真实 Citation ID、locator 和 Claim 绑定，检查存在性、候选归属、版本与权限。
4. 候选合法不是事实支持证明。校验 Claim 与正文支持关系，至少覆盖数字、日期、条件、否定和版本差异。
5. Judge 是辅助，非法结果/超时不得放行；还存在合法补证机会时回到 Agent，否则 uncertain/refused。
6. 最终 Markdown 只从通过校验的 Claims 和 Citation 渲染；unsupported 事实不能出现在 answered。
7. Claims、Citation、最终 Message 和 Run 终态以幂等事务提交；事件/outbox 协议确保提交后才发布 completed。

Given 文档讲考勤，模型却回答“每人百万美元奖金”；Then 不得 answered，即使某组由证据重新生成的 Claims 被标为 supported。此项为 ND-AGENT-01 的必测回归。

首版采用保守策略：任一事实 Claim 未通过支持校验，整份候选答案不发布；经合法补证并全量校验通过才可 answered。局部删句发布需后续独立 ADR，不能默认忽略非法 Claim 而保留全文。

## 8. 持久化、恢复与执行生命周期

### 8.1 Checkpointer 和事实源

测试使用 InMemorySaver + 真实图；生产恢复使用经版本验证的 PostgreSQL Checkpointer。Checkpointer 是执行状态，不替代 Run/Message/Claims/Citation 业务事实。

服务端生成一 Run 一 thread_id。并发 Run 不共写 checkpoint；对话历史通过受授权业务 Message 加载。图、State、Prompt、工具与模型版本随 Run 固定；恢复时不静默换图。

### 8.2 单执行者与一致性

通过数据库租约/条件认领和 fencing/状态版本保证一个有效执行者；进程内 set/线程锁不足以承担跨进程要求。明确 checkpoint、Run、ProviderCall 和公开事件的幂等/对账协议。

工具动作登记稳定标识，重放不重复发布答案、追加同一事件或重复有效副作用。checkpoint 不保证外部 LLM 调用/计费 exactly-once；供应商不支持幂等时记录尝试、用量和残余计费风险。

BackgroundTasks/线程仅可作为开发夹具；持久化切片须实现独立执行入口、租约续期/超时与恢复扫描，和文档 parse 队列隔离。

### 8.3 澄清恢复

使用 interrupt 与 Command(resume=...) 恢复同一 Run，澄清次数和预算不清零。恢复鉴权、请求幂等、状态约束和错误映射必须有契约/安全测试。

公开恢复 endpoint/字段暂未冻结；现有 OpenAPI contract-v0.1 不含该能力。ND-AGENT-03 在 M00 冻结对应接口并验证消费者前 blocked，业务代码不得私加接口。

interrupt 节点恢复会重跑部分前置代码；不可将非幂等审计、计费或写操作放入会重复执行的片段。

## 9. Run 状态、SSE 和取消

- 使用 SPEC §3.2 的粗粒度公开 Run 状态，内部 agent/tools 循环不新增公开枚举。
- planning → retrieving 内部可循环；形成候选后 drafting → verifying；有限补证按新规格 verifying → retrieving。
- 澄清可在 planning/retrieving 进入 waiting_for_user，恢复后 resuming → retrieving。
- 任一非终态可取消；每个调用边界重检取消，尽可能取消等待中的外部调用；晚到结果不得覆盖 cancelled。
- SSE 沿用 contract-v0.1 信封和事件名，图阶段投影到已允许的公开阶段；新的 payload 字段必须经消费者契约批准。
- 只发白名单脱敏行动摘要，不透传原始 LangGraph 事件、Prompt、Thought、工具原始参数或受保护 Observation。
- 首版最终文本通过校验和持久化后才发送 token/citation/completed；校验前仅推送阶段进度，不把草稿显示成正式答案。
- seq 由持久化协议保证按 Run 递增；终态唯一；SSE 重连只重放，不触发 Agent 再执行。

## 10. 模型与部署能力

模型适配须支持工具 schema、调用 ID、严格参数、ToolMessage 回传、结构化 Finalizer、用量和取消/超时。主备模型分别验证能力与数据政策，OpenAI-compatible 不代表完整工具能力。

框架及模型适配版本由 M03/M11 在 Python 3.12 环境验证、锁定并登记。新 Agent 模式缺依赖、缺工具能力或配置不足时启动/请求失败，不静默回落线性 RAG。

可使用 langchain-core 消息/工具与供应商适配包，但 LangGraph StateGraph 是必需编排运行时。真实模型只用批准的低敏/脱敏样本冒烟，真实密钥不提交；Fake 行为通过不代表 live 通过。

## 11. 测试、DoR/DoD 与交付

### 11.1 首批测试

除 §2 登记测试外，必须覆盖不同 Observation 改变工具序列、无工具能力拒绝、无证据拒答、候选外/悬空 Citation、外发禁止、文档注入、跨用户/跨 Run 上下文、重复请求、预算耗尽、取消竞态、SSE 重连和 checkpoint 恢复。

Fake/Stub 只替换模型与外部服务，不替换 StateGraph 或把期望动作硬编码进业务路由。真实 Postgres 重启/租约和供应商冒烟单独归档。

Agent Golden Set 记录问题、允许工具/权限、关键观察、期望证据与终态，不将唯一固定工具轨迹作为所有题的答案。评价证据覆盖、事实支持、越权阻断、调用成功、成本与耗时；阈值仍由实测/业务复核冻结。

### 11.2 切片依赖

| 工单 | 内容 | 当前可开工性 |
|---|---|---|
| ND-AGENT-01 | 答案门禁回归与修复 | done（迁移基线安全子集；完整原文支持门禁；无新公开接口） |
| ND-AGENT-02 | 工具/模型/预算内部 Contract + 真实 StateGraph 最小闭环 | blocked；01 已完成，仍须 DR-010 与锁依赖 Contract |
| ND-AGENT-03 | Run/SSE/澄清恢复与 Web 集成 | blocked；ND-AGENT-02、公开恢复/错误映射 Contract |
| ND-AGENT-04 | Claims/Citation、checkpoint、租约、事件一致性 | blocked；ND-AGENT-03、DR-011 与迁移 Contract |
| ND-AGENT-05 | 真实模型工具能力及 Agent Golden Set | blocked；前序闭环、批准环境/样本/密钥 |

### 11.3 完成标准

需求 accepted 不等于实施切片 DoR 完成；每刀先冻结接口、注入策略和 Red 测试。完成需有真实图执行、多轮自主工具选择、全部安全负向测试、持久化/恢复证据、公开契约一致与进度归档。

现有 30 项 QA/Run/SSE 测试通过只能证明旧覆盖；608 项历史回归、合成/脱敏 Golden Set、Compose 文件与框架依赖不能证明 FR-AGENT 已实现或任何 GATE 已通过。

## 12. 文档迁移清单

| 文件 | 当前用途 |
|---|---|
| [SPEC.md](../SPEC.md) | SPEC-1.1，全局规范源；旧线性主图已替换 |
| 本文件 | FR-AGENT 专项规范；受 SPEC 管理 |
| [MODULE_SPEC.md](../MODULE_SPEC.md) | M00/M01/M03/M05/M06/M08/M09/M11 责任地图 |
| [ADR-009](../progress/changes/20261002-M00-langgraph-react-baseline.md) | 取代旧 LangGraph 暂缓与固定主图裁决 |
| [20260906-M05-langgraph.md](../progress/changes/20260906-M05-langgraph.md) | superseded，历史申请，不再阻断当前路线 |
| [next-dev-spec.md](../progress/next-dev-spec.md)、[tickets.md](../progress/tickets.md) | 新 Agent 关键路径优先；旧 Wave 3/STG/P0 记录保留 |
| 技术方案 GPT / V2 / A3 | 历史工程/产品/交互参考，不再独立决定 Agent 架构 |
| .pi/artifacts/Pivot-LangGraph-ReAct改造方案.md | 已被本规范取代的讨论稿，不是实施依据 |

不批量删除文件；历史提交、证据、tag、需求 ID 和旧实现事实保留。新增恢复接口和机器 schema 在后续 Contract 切片发布，不把未实现能力伪装为当前可用 API。

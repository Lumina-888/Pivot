# SPEC-1.1 剩余工作 Tickets

> **版本 / 日期**：TICKETS-1.5 / 2026-10-03。
> **需求源**：[SPEC-1.1](../../SPEC.md)、[AGENT-SPEC-1.0](../../spec/AGENT_SPEC.md)；责任边界：[MODULE-SPEC-1.2](../../MODULE_SPEC.md)。
> **进度快照**：[PROGRESS.md](../../PROGRESS.md)、[验收矩阵](../../spec/acceptance/matrix.md)；已提交实现基线 `8cd4727`（main）。
> **性质**：剩余工作拆分，不是新规格、契约发布或验收报告。既有父票和历史完成记录见 [tickets.md](../tickets.md)。

## 0. 拆分口径

- ND-AGENT-01 已完成答案安全迁移子集，证据见 [nd-agent-01.md](../../evidence/agent-m05/nd-agent-01.md)。不重开已修漏洞；完整事实事务、outbox 与真实图仍需后续票。
- Wave 0~3/STG 已完成项保留，不重复安排脚手架、HTTP 接线、native extra 或十页 Mock 实现。`wave-3-integrated` 不等于 ReAct 或任一 P0 门禁通过。
- FR-AGENT-001~010 尚未完整实现/验收；GATE-P0-001~008 全部 unverified；企业集 120 条为脱敏摘录，不等于业务复核/live 检索。
- 本次只读核对源码与版本化证据。工作区已有 6 个业务源码修改及用户未跟踪文件不纳入本次拆票，不据此提高实现/验收状态。
- 子票沿用父票 ID 加 `-A` 等后缀；新发现的跨域缺口使用 `ND-GAP-*`。不新增需求 ID、公开接口、状态、错误码或预算默认值。
- `ready` 在本文件仅表示 **Contract 调研/提案、Red 设计可开始**，不表示业务实现 DoR 已满足。实现票保持 `blocked`，经已发布 Contract、Owner 决策与依赖证据确认后才能开工。父票不因一张前置子票完成而自动 done。
- 以下测试名、交付路径均为 **计划**，除明确引用历史证据外不是现有测试或通过结果。规模 S 约一个主线切片，M 约 2~3 个串行切片；不授权子代理、并行写入或新建 worktree。

## 1. 执行索引

最新 [02-A/B/C 审核与待签清单](../../evidence/agent-m03/nd-agent-02-abc-review.md)：02-B draft.2 补独立累计/执行前门禁，Windows 技术20 probes passed；Linux 本机无 Docker、WSL/Bash 0x80070422 blocked，[原生执行单](../../evidence/agent-m03/nd-agent-02-c/linux-validation.md)未执行。消费者/Owner/安全 pending，无代签；02-A/B/C review，02-D～H blocked 不变。

优先顺序：ND-AGENT-02-A → 02-B → 02-C → 02-D/E/F → 02-G/H → 03 → 04 → 05。02-A/B/C 已提交 proposed 提案，均 review 待消费者/Owner 签认；02-C Windows 受控验证/候选锁已提交，Linux/预算映射审核待补齐，不解锁业务实现。03-A [恢复提案](../changes/20261003-M00-agent-resume-contract.md)已提交 proposed，review 待签认；04-A 可提前编写提案，均不能提前发布恢复接口或运行持久化实现。每一段均在 main 串行执行。

| 子票 | 工作 | 优先级 / 规模 | Accountable | 状态 | 硬依赖 / 放行条件 |
|---|---|---|---|---|---|
| ND-AGENT-02-A | 模型、工具、State 与 EvidenceRegistry 内部 Contract | P0 / S | M05 | review | proposed 提案/Red 设计已提交；消费者/Owner 待签认，非发布 |
| ND-AGENT-02-B | DR-010 预算策略与累计用量 Contract | P0 / S | M05 | review | proposed 提案/有限 Fixture/Red 设计已提交；消费者/Owner 待签认，非发布 |
| ND-AGENT-02-C | Python 3.12 框架/消息/适配依赖验证与锁定方案 | P0 / S | M03 | review | Windows 验证/候选哈希锁已提交；Linux/消费者/Owner 审核未完成，非发布 |
| ND-AGENT-02-D | 两个只读工具与本 Run 证据注册 | P0 / M | M05 | blocked | 02-A/B/C Contract；DR-010 受控执行策略 |
| ND-AGENT-02-E | 可信上下文、历史与每次调用外发门禁 | P0 / M | M01 | blocked | 02-D；02-A/B/C Contract |
| ND-AGENT-02-F | 调用、重写、重试及主备累计预算 | P0 / M | M05 | blocked | 02-A/B/C；DR-010 受控执行策略 |
| ND-AGENT-02-G | 真实 StateGraph 原生工具条件循环 | P0 / M | M05 | blocked | 02-D/E/F |
| ND-AGENT-02-H | Finalizer/Verifier 补证与全量答案门禁接图 | P0 / S | M05 | blocked | 02-G；01 安全回归 |
| ND-AGENT-03-A | 恢复 API、错误映射与消费者 Contract 提案 | P0 / S | M00 | review | proposed schema/形状检查/用例设计已提交；发布须 02 闭环/消费者确认 |
| ND-AGENT-03-B | 新图到 Run 状态/SSE 白名单投影 | P0 / S | M05 | blocked | 02-H；已批准事件/状态 Contract |
| ND-AGENT-03-C | 调用边界取消与晚到结果竞争 | P0 / S | M05 | blocked | 03-B |
| ND-AGENT-03-D | 一轮 interrupt 与授权幂等 resume | P0 / M | M05 | blocked | 03-A 发布；03-B/C |
| ND-AGENT-03-E | Web 恢复/等待/取消与 SSE 消费 | P1 / M | M08 | blocked | 03-D；03-A 发布 |
| ND-AGENT-04-A | DR-011 checkpoint/租约/事实/outbox 迁移 Contract | P0 / M | M03 | ready | 仅提案；发布须 03 关闭/治理审核 |
| ND-AGENT-04-B | Claims/Citation/Message/终态事务与 outbox | P0 / M | M03 | blocked | 04-A 发布；03 关闭 |
| ND-AGENT-04-C | PostgreSQL Checkpointer 与版本固定恢复 | P0 / M | M03 | blocked | 04-A/B；DR-011 |
| ND-AGENT-04-D | 数据库租约/fencing 与独立在线执行入口 | P0 / M | M03 | blocked | 04-B/C；03-C |
| ND-AGENT-04-E | ProviderCall 尝试/用量与恢复对账 | P0 / S | M06 | blocked | 04-A/B/D；02-F |
| ND-AGENT-04-F | 真实 PG 宕机、争用与重放故障矩阵 | P0 / M | M11 | blocked | 04-B/C/D/E；受控 PG 环境 |
| ND-AGENT-05-A | 主备原生工具模型 HTTP Adapter | P0 / M | M05 | blocked | 02 Contract、04-F；模型能力/政策确认 |
| ND-AGENT-05-B | 主备 live 工具能力冒烟 | P0 / S | M11 | blocked | 05-A；批准样本/密钥/预算/环境 |
| ND-AGENT-05-C | Agent Golden Set schema 与 Fake 图回归 | P0 / M | M11 | blocked | 03/04 闭环；业务场景确认 |
| ND-AGENT-05-D | Agent live 质量、成本与安全评测 | P0 / M | M11 | blocked | 05-B/C；ND-P0-01-A；批准环境 |
| ND-GAP-01 | 后台 metrics/tasks Contract 与真实接线 | P1 / M | M11 | blocked | M00 字段/分页/路径所有权确认 |
| ND-GAP-02 | 持久审计统一接线与重启可复盘 | P0 / M | M06 | blocked | M03 Repository/迁移 Contract；M00 审核 |
| ND-GAP-03 | 首次改密/重置后的跨实例生命周期验收 | P0 / S | M01 | blocked | M00/M03 机制确认；不得私加字段 |
| ND-GAP-04 | 签名导出下载消费者与过期/授权端到端验收 | P1 / M | M06 | blocked | M00 下载消费者 Contract；04-B；TTL 策略 |
| ND-P0-01-A | 120 条企业脱敏集业务复核 | P0 / M | M11 | blocked | Owner 指定业务复核人/样本准入 |
| ND-STG-04-A | staging ECS apply 与低敏冒烟 | P1 / M | M11 | blocked | Owner SSH/安全组/磁盘/访问拓扑 |

共 29 张细化票：23 张 Agent 子票、4 张跨域缺口票、2 张人工/环境余量票。当前 1 张 ready（04-A）只开放前置调研；02-A/B/C 与03-A 共4张 review（proposed 待签认），24张 blocked，没有业务实现票解锁。P0/P1 既有门禁票继续沿用，见 §4。

## 2. Agent Tickets

### ND-AGENT-02-A 内部模型/工具/状态契约

- **父票 / 来源 / 责任**：ND-AGENT-02；FR-AGENT-001/002/003/009，AGENT_SPEC §3~5/§10；Accountable M05，Contributors M00/M01/M03/M04/M06/M11。
- **状态 / 依赖**：review；ND-AGENT-01 done；[AGENT-INTERNAL-0.1-draft.1 提案](../changes/20261002-M05-agent-internal-contract.md)与 Red 设计已提交，消费者/Owner 均 pending，不是已发布契约或 done。
- **场景 / 异常**：Given 模型返回行动；When 解码；Then 只接受单个合法 tool_call 或 finalize/clarify/refuse 控制意图；未知工具、多调用、额外参数、无调用 ID、非法结构 fail closed，不作临时故障重试。
- **范围 / 数据**：定义模型能力、AIMessage/ToolMessage 关联、严格工具参数、可信 RunContext 与可序列化 AgentState 分界、EvidenceRegistry 来源/去重、Finalizer 输入输出及内部错误分类；供应商端口不泄漏 URL/key。
- **路径 / 交付**：`progress/changes/` 内部 Contract 提案；按 Owner 确认的 `spec/contracts/` 内部说明与 Fake 消费者用例设计。业务端口落地归 02-D/F/G。
- **计划测试**：`test_FR_AGENT_002_extra_tool_arguments_rejected`、`test_FR_AGENT_001_tool_message_matches_call_id`、`test_FR_AGENT_009_tool_capability_required`；提案 §8 有完整 Given/When/Then 与 Fake 失败判据，运行时测试未实施。
- **DoD / 证据**：各消费者确认版本、输入/输出/错误与兼容策略；记录不能外发/不能序列化的数据清单。未批准前只是 proposed，不解锁 02 实现。
- **本轮证据**：[nd-agent-02-a.md](../../evidence/agent-m05/nd-agent-02-a.md)；4 份拟议 schema 的 10 正向/28 负向形状检查、公共契约 48 与既有 QA/Run/SSE 79 回归通过；不证明工具运行时行为，不解锁父票。
- **不做**：不增加 resume 路由，不以自由文本正则模拟 tool calling，不安装依赖冒充 ReAct 验收。

### ND-AGENT-02-B DR-010 预算 Contract

- **父票 / 来源 / 责任**：ND-AGENT-02；FR-AGENT-004、FR-STREAM-005，AGENT_SPEC §6；Accountable M05，Contributors M00/M06/M11。
- **状态 / 依赖**：review；[AGENT-BUDGET-0.1-draft.2 提案](../changes/20261002-M05-agent-budget-contract.md)、有限 Fixture 与 Red 设计已提交，消费者/Owner 均 pending；未发布、DR-010 未关闭，生产数值仍 TBD-P0。
- **场景 / 异常**：Given 重写、同 query 重复调用、基础设施重试或主备切换；Then 使用同一累计账本；无必需运行策略时 fail closed，不能使用 recursion_limit 代替业务预算。
- **范围 / 数据**：冻结维度、单位、预扣/结算、耗尽终态、配置缺失错误、观察截断与上下文窗口策略；覆盖模型/工具数、单步/总时长、token/费用、并发、recursion_limit。保留 rewrite≤2、clarification≤1 已定约束。
- **路径 / 交付**：`progress/changes/` DR-010 提案、预算 Contract、明确注入有限值的测试 Fixture 与受控实验计划。
- **计划测试**：`test_FR_AGENT_004_missing_policy_fails_closed`、`test_FR_AGENT_004_repeated_query_consumes_budget`、`test_FR_STREAM_005_fallback_does_not_reset_budget`。
- **DoD / 证据**：M05/M11 确认策略与 Fixture，Owner 明确受控运行配置批准范围；需要冻结的数值附实测/ADR 并回写规范。仅 schema 完成不等于 DR-010 全部关闭。
- **本轮证据**：[nd-agent-02-b.md](../../evidence/agent-m05/nd-agent-02-b.md)；2 个拟议 schema 的正负形状检查及有限账本示例算术检查，18 组运行时 Red 仅登记计划；不是预扣/恢复/并发或主备执行验收。
- **不做**：不私设生产默认，不把 Fixture 值、配置 example 或后续 ND-P0-10 汇总当批准依据。

### ND-AGENT-02-C 框架依赖与锁定

- **父票 / 来源 / 责任**：ND-AGENT-02；FR-AGENT-009，AGENT_SPEC §8.1/§10；Accountable M03，Contributors M05/M11。
- **状态 / 依赖**：review；[依赖/锁定申请](../changes/20261002-M03-agent-dependencies-lock.md)与 Windows CPython 3.12 候选已提交，六项审核 pending；Linux/预算映射/正式依赖发布未完成，非 done。
- **场景 / 异常**：Given 启用 Agent 模式；Then StateGraph、消息/工具接口及 checkpointer 版本兼容；缺依赖/不支持 tools 失败，不静默切旧线性实现。
- **范围 / 数据**：确认 LangGraph/langchain-core/模型适配/checkpointer 版本组合、锁文件策略、CI/Docker 安装范围及升级/回滚限制；版本须随 Run 追踪。
- **路径 / 交付**：`progress/changes/` 依赖申请；批准后由 M03 串行维护 `api/pyproject.toml`/锁文件，M11 同步 CI/镜像。
- **计划测试**：`test_FR_AGENT_009_missing_graph_dependency_fails_closed`、`test_FR_AGENT_006_checkpoint_version_compatible`。
- **DoD / 证据**：Python 3.12 版本矩阵、受控导入/消息序列化验证与可重建锁定记录；无未经批准包或生产安装声明。
- **本轮证据**：[nd-agent-02-c.md](../../evidence/agent-m03/nd-agent-02-c.md)；111 个精确 wheel 哈希、两个隔离环境离线重建/11 技术探针、含候选的既有 661 passed/19 skipped。确认 None 恢复 limit+2、strict 字典 passthrough、serde 不脱敏；02-B 预算硬门禁须签认。未改 pyproject/正式锁/CI/镜像，未验证 PG/Linux/live，不解锁业务票。
- **不做**：不承诺仅安装 LangGraph 就完成 FR-AGENT-001，不默认升级无关依赖。

### ND-AGENT-02-D 只读工具与 EvidenceRegistry

- **父票 / 来源 / 责任**：ND-AGENT-02；FR-AGENT-002、FR-RAG-002/003/005/006；Accountable M05，Contributors M01/M04。
- **状态 / 依赖**：blocked；02-A/B/C Contract 与 DR-010 受控执行策略。
- **场景 / 异常**：Given search_knowledge 已登记候选；When read_evidence；Then 只读取本 Run 合法 evidence_id，并重新检查版本/删除/期限/权限/外发；猜测他 Run ID 不泄露存在性。
- **范围 / 数据**：复用 M04 混合检索；服务端注入 principal/scope；严格单参数 schema、限长观察、按版本去重保留来源/调用 ID、冲突元数据；历史引用须重新解析授权登记。
- **路径 / 交付**：`api/src/pivot/qa/**`；跨 M04/M01 的端口修改先走变更申请；`tests/unit/qa/**`、`tests/security/retrieval/**`。
- **计划测试**：`test_FR_AGENT_002_read_only_tools`、`test_FR_AGENT_002_foreign_run_evidence_rejected`、`test_FR_RAG_003_tool_scope_cannot_expand`。
- **DoD / 证据**：合法搜索/读证据与未知工具、额外字段、已删/过期/权限变更负向报告；所有 evidence 可追溯原 Chunk 与版本。
- **不做**：不增加联网/Shell/SQL/写工具，不复制另一套检索算法。

### ND-AGENT-02-E 可信上下文与外发

- **父票 / 来源 / 责任**：ND-AGENT-02；FR-AGENT-003、FR-RBAC、SPEC §8.3；Accountable M01，Contributors M05/M04/M03。
- **状态 / 依赖**：blocked；02-D 与 02-A/B/C Contract。
- **场景 / 异常**：Given 客户端/模型伪造身份、scope 或文档含指令；Then 不扩大权限；受限正文及其摘要/历史不能发送给任一外部 Planner/Finalizer/Verifier/备用模型。
- **范围 / 数据**：服务端重建 RunContext；授权历史窗口、Observation 与衍生数据；每次模型/工具调用前后检查 active/owner/scope/最新文档资格；恢复重检逻辑供 03-D/04-C 复用。
- **路径 / 交付**：`api/src/pivot/auth/**`、`security/**` 及 M05 调用边界；`tests/security/auth/**`/Agent 安全集成测试。
- **计划测试**：`test_FR_AGENT_003_model_cannot_expand_scope`、`test_FR_AGENT_003_restricted_history_never_sent`、`test_FR_AGENT_003_document_injection_cannot_change_tools`。
- **DoD / 证据**：逐个调用角色与主备的数据外发负向报告；跨用户/跨 Run 隔离；checkpoint 不含凭证/依赖句柄。
- **不做**：不靠 Prompt 授权，不通过换供应商绕过外发禁止，不在此票决定新 ACL。

### ND-AGENT-02-F 累计预算与重试

- **父票 / 来源 / 责任**：ND-AGENT-02；FR-AGENT-004、FR-STREAM-005；Accountable M05，Contributors M06/M11。
- **状态 / 依赖**：blocked；02-A/B/C 与 DR-010 受控执行策略。
- **场景 / 异常**：首次搜索不算 rewrite，后续 query 改变计 rewrite；重复 query 仍消耗调用预算；超时/429/临时5xx/网络错误可有限重试，非法格式/权限/外发不可重试。
- **范围 / 数据**：调用前预检、返回后用量登记、稳定 step/attempt、主备累计、单步/总超时与观察限长；AgentState 保存预算游标以供 04-C 恢复。
- **路径 / 交付**：`api/src/pivot/qa/**`、`runs/**`、`tests/unit/qa/**`、`tests/unit/runs/**`；M06 提供 ProviderCall 端口。
- **计划测试**：`test_FR_AGENT_004_rewrite_limit_enforced`、`test_FR_AGENT_004_fallback_shares_budget`、`test_FR_STREAM_005_protocol_error_not_retried`。
- **DoD / 证据**：明确注入 Fixture 的耗尽/重试/切换测试与用量账本；安全终态没有未验证正文；记录实际用量缺失的处理策略。
- **不做**：不清零预算，不以内存测试宣称生产恢复完成（恢复测试由 04-F 验证）。

### ND-AGENT-02-G 真实 StateGraph 工具循环

- **父票 / 来源 / 责任**：ND-AGENT-02；FR-QA-001、FR-AGENT-001；Accountable M05，Contributors M04/M11。
- **状态 / 依赖**：blocked；02-D/E/F。
- **场景 / 异常**：Given scripted Fake 模型收到不同合法 Observation；Then 选择不同后续工具或结束；合法空观察可新查询，无预算或无合法路径则安全结束。
- **范围 / 数据**：START/agent/tool_guard/tools/observation_guard 条件边与消息状态；一个响应最多执行一个工具；用真实 StateGraph 与 InMemorySaver 测试，稳定工具调用 ID。
- **路径 / 交付**：`api/src/pivot/qa/**`、`tests/unit/qa/**`；图运行与节点覆盖报告。
- **计划测试**：`test_FR_AGENT_001_observation_drives_next_tool`、`test_FR_AGENT_001_empty_observation_changes_query`、`test_FR_AGENT_002_multiple_calls_fail_closed`。
- **DoD / 证据**：至少两种观察分支及搜索→改写/读证据→结束路径可回放；Fake 只替换模型/外部服务，不替换图或硬编码固定工具序列。
- **不做**：不把旧线性函数包装成图验收，不宣称跨进程/公开恢复可用。

### ND-AGENT-02-H 答案门禁与补证接图

- **父票 / 来源 / 责任**：ND-AGENT-02；FR-QA-002/003/004、FR-AGENT-005；Accountable M05，Contributors M06/M11。
- **状态 / 依赖**：blocked；02-G、ND-AGENT-01 安全基线。
- **场景 / 异常**：Given 候选支持不足；Then 仅在合法补证且有预算时 verify→repair_feedback→agent；任一 Claim 未通过仍整份不发布，Judge 故障不放行。
- **范围 / 数据**：独立 structured_finalize、真实 Citation 绑定、支持校验、受控渲染与 persist_result 端口；覆盖数字/日期/条件/否定/版本冲突；旧完整原文策略保留直到 DR-004 批准替代。
- **路径 / 交付**：`api/src/pivot/qa/**`、`tests/unit/qa/**` 与 HTTP/消息/导出回归。
- **计划测试**：`test_FR_AGENT_005_unverified_markdown_never_published`、`test_FR_QA_004_repair_requires_budget`、`test_FR_QA_003_exhausted_empty_search_refused`。
- **DoD / 证据**：ND-AGENT-01 全部负向回归在真实图路径通过；校验前无正式正文；02 父票按 Fake 图范围收口并列明持久化余量。
- **不做**：不局部删句发布，不在 DR-004 未关闭时私设语义 Judge 阈值；事务/outbox 归 04-B。

### ND-AGENT-03-A 恢复公开契约

- **父票 / 来源 / 责任**：ND-AGENT-03；FR-QA-006、FR-AGENT-007、SPEC §5.4；Accountable M00，Contributors M01/M03/M05/M08/M09。
- **状态 / 依赖**：review；[AGENT-RESUME-0.1-draft.1](../changes/20261003-M00-agent-resume-contract.md)与独立 proposed schema/62项形状检查/运行时 Red 设计已提交，待消费者签认；发布/消费者代码依赖02闭环及Owner审核，未新增可调用API。
- **场景 / 异常**：Given owner 对 waiting_for_user 的 Run 回复；Then 恢复同一 Run；重复键同参数幂等、不同参数冲突；非 owner、停用、错误状态、第二轮澄清与终态拒绝。
- **范围 / 数据**：明确 endpoint/字段/鉴权/幂等/错误映射、状态约束和契约版本兼容；等待期限仍 TBD-P0，未经决策不写默认。服务端 thread_id 不作为客户端授权参数。
- **路径 / 交付**：`progress/changes/`、`spec/contracts/**`、`spec/scenarios/qa.feature`、`tests/contract/` 根级；消费者签认。
- **计划测试**：`test_FR_AGENT_007_resume_contract_owner_required`、`test_FR_AGENT_007_resume_idempotency_conflict`。
- **DoD / 证据**：机器 schema、错误与消费者用例一致，兼容窗口/升级说明获批；仅提案不能标可调用 API。
- **本轮证据**：[nd-agent-03-a.md](../../evidence/agent-m00/nd-agent-03-a.md)；62项字段/类型/错误配对/未发布边界检查通过，运行时owner/幂等/取消/恢复测试仍未实施；7项签认pending，不解锁03父票。
- **不做**：不在当前 contract-v0.1 私加路由，不提前生成发布客户端。

### ND-AGENT-03-B Run/SSE 投影

- **父票 / 来源 / 责任**：ND-AGENT-03；FR-QA-005、FR-STREAM-002/003、FR-AGENT-008；Accountable M05，Contributors M00/M08。
- **状态 / 依赖**：blocked；02-H、公开状态/事件映射获确认。
- **场景 / 异常**：内部 agent/tools 循环保持 retrieving；有限补证 verifying→retrieving；校验前仅白名单阶段摘要；校验且提交后才发送 token/citation/completed。
- **范围 / 数据**：SPEC §3.2 合法转移、粗粒度 stage 投影、终态唯一、Last-Event-ID 重放与状态查询降级；不得透传 raw LangGraph event。
- **路径 / 交付**：`runs/**`、`stream/**`、`tests/unit/runs/**`、`tests/contract/stream/**`。
- **计划测试**：`test_FR_AGENT_008_public_events_hide_internal_messages`、`test_FR_STREAM_003_reconnect_does_not_execute_agent`、`test_FR_STREAM_002_terminal_event_unique`。
- **DoD / 证据**：事件 schema/seq/状态转换与 ND-AGENT-01 正文门禁回归通过；跨进程序号与 outbox 最终由 04-B/F 验收。
- **不做**：不新增 agent/tools 公开枚举，不把 SSE 连接关闭当 Run 终态。

### ND-AGENT-03-C 取消与晚到结果

- **父票 / 来源 / 责任**：ND-AGENT-03；FR-STREAM-004、FR-AGENT-008；Accountable M05，Contributors M01/M03/M11。
- **状态 / 依赖**：blocked；03-B。
- **场景 / 异常**：Given 调用等待中取消；Then 尽可能传播取消，并在调用返回/持久发布前重检；晚到答案不能覆盖 cancelled；重复取消幂等，已完成终态不改写。
- **范围 / 数据**：所有模型/工具/Verifier 边界、状态条件更新与取消句柄；HTTP owner/admin 授权及竞态测试；持久 fencing 归 04-D。
- **路径 / 交付**：`qa/**`、`runs/**`、模型/检索取消端口及 pipeline 测试。
- **计划测试**：`test_FR_AGENT_008_cancel_blocks_late_answer`、`test_FR_STREAM_004_cancel_terminal_is_idempotent`。
- **DoD / 证据**：可控阻塞 Fake 复现取消/完成竞争，无正文/Message/导出泄漏；记录供应商不支持真正中断的限制。
- **不做**：不声称取消可撤销已发生计费；真实多进程竞争归 04-F。

### ND-AGENT-03-D interrupt 与授权 resume

- **父票 / 来源 / 责任**：ND-AGENT-03；FR-QA-006、FR-AGENT-007/004；Accountable M05，Contributors M01/M00/M03。
- **状态 / 依赖**：blocked；03-A 已发布、03-B/C。
- **场景 / 异常**：Given 第一轮澄清；Then interrupt 保存状态，经 owner 回复 Command(resume=...) 回到同一 Run；次数/预算不清零，跨用户/重复恢复/第二轮澄清不能绕过门禁。
- **范围 / 数据**：开发夹具 InMemorySaver、等待/恢复状态、恢复重建上下文、最新授权/外发/资源/预算检查；interrupt 重跑片段中的审计/调用必须幂等。
- **路径 / 交付**：`qa/**`、`runs/**`、安全/契约/集成用例；公开路由只消费 03-A 批准版本。
- **计划测试**：`test_FR_AGENT_007_resume_is_owner_isolated`、`test_FR_AGENT_004_budget_survives_resume`、`test_FR_AGENT_007_second_clarification_rejected`。
- **DoD / 证据**：等待→恢复同 Run、重复恢复、权限撤销、文档删除与预算耗尽的 Fake 图报告；明确生产持久恢复待 04。
- **不做**：不接受客户端提供任意 checkpoint thread；不冻结等待超时。

### ND-AGENT-03-E Web 消费者

- **父票 / 来源 / 责任**：ND-AGENT-03；FR-AGENT-007/008、FR-STREAM-002/003/004、NFR-UX-001~004；Accountable M08，Contributors M09/M11。
- **状态 / 依赖**：blocked；03-A 发布与 03-D。
- **场景 / 异常**：Given 等待澄清、断线、取消或终态；Then UI 与后端状态一致；重复事件不重复答案，重连不重新提交 Run，未校验草稿不显示为正式答案。
- **范围 / 数据**：共享 API/SSE client 类型与等待/恢复动作；M09 对话页加载/错误/拒答/取消/澄清状态、引用抽屉；键盘/焦点/aria-live/reduced-motion。
- **路径 / 交付**：M08 `web/lib/api/**`/`stream/**`，M09 `web/features/user/**`；Fake 消费者与 opt-in 浏览器测试。
- **计划测试**：`test_FR_AGENT_007_web_resume_same_run`、`test_FR_STREAM_003_web_replay_deduplicates`、`test_NFR_UX_003_clarification_announced`。
- **DoD / 证据**：Web test/typecheck/lint 与十页回归；浏览器澄清/断线/取消/引用截图与自动化报告分开归档。
- **不做**：不改十页范围，不存长期凭证，不通过前端隐藏代替鉴权。

### ND-AGENT-04-A DR-011 与迁移契约

- **父票 / 来源 / 责任**：ND-AGENT-04；FR-AGENT-006、FR-QA-002、SPEC §2/§7.3；Accountable M03，Contributors M00/M01/M05/M06/M11。
- **状态 / 依赖**：ready，仅 proposed 设计；发布与迁移实现须 03 关闭、DR-011/Owner 审核。
- **场景 / 异常**：Given 崩溃/并发/取消；Then checkpoint、Run、结果、事件与调用尝试有明确提交/重放边界，不能由 Redis/进程锁承担唯一事实。
- **范围 / 数据**：checkpoint 表/保留/加密/删除/访问/备份、thread/State/图版本、租约/fencing、结果 Unit of Work、outbox/序号唯一性、ProviderCall 尝试/对账与迁移回滚。
- **路径 / 交付**：`progress/changes/` ADR/迁移 Contract；`spec/contracts/` 内部说明与 M03/M05/M06/M11 消费者确认。
- **计划测试**：`test_FR_AGENT_006_fencing_rejects_stale_executor`、`test_FR_AGENT_006_checkpoint_has_no_credentials`、`test_FR_QA_002_result_transaction_rolls_back`。
- **DoD / 证据**：一致性时序/故障窗口、敏感治理、迁移/回滚与调用重复计费残余风险获签认；不存在偷偷冻结保留期。
- **不做**：不把 checkpoint 当业务事实，不宣称框架自动 exactly-once。

### ND-AGENT-04-B 结果事务与 outbox

- **父票 / 来源 / 责任**：ND-AGENT-04；FR-QA-002、FR-AGENT-005、FR-STREAM-001/002；Accountable M03，Contributors M05/M06/M00。
- **状态 / 依赖**：blocked；04-A 已发布、03 关闭。
- **场景 / 异常**：Given 已校验候选；Then Claims/Citation/最终 Message/Run 终态同事务幂等提交；提交失败不发正文，提交后进程崩溃可从 outbox 重放，唯一终态/seq 不重复。
- **范围 / 数据**：引用/版本外键与候选重新校验、结果事务、事件 outbox、SQL Repository；导出/会话消息改读持久事实，取消竞争条件更新。
- **路径 / 交付**：`api/src/pivot/db/**`、`migrations/**`；M05/M06 消费端口与 pipeline 回归。
- **计划测试**：`test_FR_QA_002_claims_citations_message_commit_atomically`、`test_FR_STREAM_002_outbox_replay_preserves_seq`、`test_FR_AGENT_005_commit_failure_publishes_nothing`。
- **DoD / 证据**：SQL 回滚、跨装配读取、提交/发送故障窗口测试；真实 PG 行为由 04-F 补全后才收父票。
- **不做**：不靠另造 Claims 背书自由 Markdown，不删除既有 Run/EventLog 兼容证据。

### ND-AGENT-04-C PostgreSQL Checkpointer

- **父票 / 来源 / 责任**：ND-AGENT-04；FR-AGENT-006/004，AGENT_SPEC §8.1；Accountable M03，Contributors M05/M01/M11。
- **状态 / 依赖**：blocked；04-A/B、DR-011。
- **场景 / 异常**：Given 节点后重启；Then 同 Run/服务端 thread 恢复工具消息、证据和已消费预算；图/State/Prompt/工具/模型版本不匹配时按批准策略拒绝或迁移，不能静默换图。
- **范围 / 数据**：锁定 PostgreSQL Saver、可信上下文重建、敏感状态治理、每 Run 独立 thread；恢复重检 active/owner/scope/外发/文档资格。
- **路径 / 交付**：M03 `db/**`/迁移，M05 Runner 接口；真实图 + PG 测试。
- **计划测试**：`test_FR_AGENT_006_restart_from_checkpoint`、`test_FR_AGENT_004_persisted_budget_survives_restart`、`test_FR_AGENT_006_restore_rechecks_authorization`。
- **DoD / 证据**：序列化与重启恢复报告，跨用户/跨 Run thread 隔离，无 Secret/reasoning 字段落库；实际抢占隔离由 04-D/F 验证。
- **不做**：不复用 Conversation ID 作为所有 Run 的 thread，不依赖旧 checkpoint 的权限快照授权。

### ND-AGENT-04-D 单执行者与在线执行入口

- **父票 / 来源 / 责任**：ND-AGENT-04；FR-AGENT-006、FR-STREAM-001/004，AGENT_SPEC §8.2；Accountable M03，Contributors M05/M11。
- **状态 / 依赖**：blocked；04-B/C、03-C。
- **场景 / 异常**：Given 两个进程认领或租约失效；Then 仅一个有效执行者，旧 fencing 不能提交晚到结果；取消与终态竞争不覆盖业务事实。
- **范围 / 数据**：PG 条件认领/续期/过期、fencing/state version、独立在线任务执行入口、恢复扫描；与 parse 队列隔离，Redis 不承担唯一恢复事实。
- **路径 / 交付**：M03 租约 Repository/迁移，M05 Runner，M11 `ops/**`/Compose 薄装配；先批准路径/队列 Contract。
- **计划测试**：`test_FR_AGENT_006_only_one_executor_per_run`、`test_FR_AGENT_006_expired_lease_cannot_publish`、`test_FR_STREAM_004_cancel_wins_stale_commit`。
- **DoD / 证据**：真实多进程竞争/失联恢复可重放；执行不依赖 HTTP BackgroundTasks 存活；额度/租约时长均来自批准策略。
- **不做**：不以进程内 set/线程锁替代数据库约束，不私设租约/并发默认。

### ND-AGENT-04-E ProviderCall 对账

- **父票 / 来源 / 责任**：ND-AGENT-04；FR-AGENT-004/006/009、FR-AUDIT-003；Accountable M06，Contributors M03/M05/M11。
- **状态 / 依赖**：blocked；04-A/B/D、02-F。
- **场景 / 异常**：Given 调用已发出而 checkpoint 未完成；Then 稳定 action/attempt 关联调用、预算和恢复；供应商支持幂等则使用，不支持时登记重复尝试/计费风险。
- **范围 / 数据**：调用前尝试、返回用量、主备/重试关联、费用估算版本与对账；不保存不必要敏感 Prompt/正文。
- **路径 / 交付**：M06 `audit/**`/ProviderCall，M03 SQL/迁移，M05 调用边界；`evidence/` 计划对账报告。
- **计划测试**：`test_FR_AUDIT_003_provider_attempt_survives_restart`、`test_FR_AGENT_004_replayed_call_does_not_reset_usage`。
- **DoD / 证据**：崩溃窗口用量可追踪，request_id/run_id/step/attempt 可关联；明确无法证明 exactly-once 的场景。
- **不做**：不将估算成本称为供应商账单，不把调用失败计成零成本。

### ND-AGENT-04-F 故障与恢复集成

- **父票 / 来源 / 责任**：ND-AGENT-04；FR-AGENT-006/007/008、FR-STREAM-001~004；Accountable M11，Contributors M03/M05/M06/M01。
- **状态 / 依赖**：blocked；04-B/C/D/E，受控真实 PG/独立执行进程。
- **场景 / 异常**：覆盖工具后、模型返回后、结果提交前/后、事件发送前/后崩溃；竞争认领、租约过期、取消、重复恢复及 SSE 重连。
- **范围 / 数据**：真实 StateGraph + PG Checkpointer/事实/outbox 与 Fake 供应商故障注入；检查唯一业务结果/终态/事件、累计预算、审计与残余重复调用。
- **路径 / 交付**：`tests/integration/**`、`tests/security/**`、`evidence/` 重启/竞争报告；Compose opt-in，CI 不擅自 build/up。
- **计划测试**：`test_FR_AGENT_006_crash_matrix_no_duplicate_publication`、`test_FR_AGENT_007_duplicate_resume_single_execution`、`test_FR_STREAM_003_reconnect_after_process_restart`。
- **DoD / 证据**：记录 PG/框架/迁移版本、真实进程数、故障点、恢复计数与风险；SQLite/InMemory 通过不能替代此报告。
- **不做**：不把本票等同全部 GATE-P0 已通过。

### ND-AGENT-05-A 原生工具 HTTP 模型适配

- **父票 / 来源 / 责任**：ND-AGENT-05；FR-AGENT-009、AGENT_SPEC §10；Accountable M05，Contributors M03/M06/M11。
- **状态 / 依赖**：blocked；02 Contract、04-F、模型能力/政策确认。
- **场景 / 异常**：Given 主/备模型响应；Then 工具 schema/call ID/ToolMessage、严格 Finalizer、用量/超时/取消均受支持；OpenAI-compatible 不等于能力通过。
- **范围 / 数据**：延续已注入的主备配置但新增原生工具协议，Fake HTTP 契约、能力拒绝、临时故障切换与每次外发门禁；版本随 Run 固定。
- **路径 / 交付**：`qa/**`，M03 适配依赖申请，M11 composition root/配置/镜像；不提交供应商 URL/key。
- **计划测试**：`test_FR_AGENT_009_http_tools_round_trip`、`test_FR_AGENT_009_fallback_requires_tool_capability`、`test_FR_STREAM_005_invalid_tool_response_not_retried`。
- **DoD / 证据**：主备 Fake HTTP 协议/用量/取消报告；真正供应商能力由 05-B 证明，不使用旧 Draft Writer 测试代替。
- **不做**：不回退线性 RAG，不为修绿放宽严格 schema。

### ND-AGENT-05-B 主备 live 能力冒烟

- **父票 / 来源 / 责任**：ND-AGENT-05；FR-AGENT-009、DR-001/007；Accountable M11，Contributors M05/M03/安全。
- **状态 / 依赖**：blocked；05-A、批准低敏/脱敏样本、密钥、预算与环境。
- **场景 / 异常**：对主/备分别验证工具选择、Observation 回传、结构化结束、用量、超时/取消；不支持工具的模型明确不可启用。
- **范围 / 数据**：opt-in 脚本和脱敏报告，供应商政策/模型版本/框架版本关联；企业真实文档仍受 ND-P0-02/05 阻断。
- **路径 / 交付**：`ops/**`、`tests/integration/**`、`evidence/` live capability 报告；CI 默认不调用。
- **计划测试**：`test_FR_AGENT_009_primary_live_tool_capability`、`test_FR_AGENT_009_fallback_live_tool_capability`。
- **DoD / 证据**：主备各自能力与限制记录，失败不改用 Fake 声称通过；成本/样本/批准范围清楚。
- **不做**：不把冒烟等同 Agent 质量评测或 GATE-P0-001 通过。

### ND-AGENT-05-C Agent Golden Set 与 Fake 回归

- **父票 / 来源 / 责任**：ND-AGENT-05；FR-AGENT-010、SPEC §10.8、AGENT_SPEC §11；Accountable M11，Contributors M00/M04/M05/业务。
- **状态 / 依赖**：blocked；03/04 闭环及场景确认；schema/标注提案可提前登记，不提前验收。
- **场景 / 异常**：覆盖观察改变行动、改写/读证据、空证据、协议非法、预算、注入、取消、跨用户/跨 Run、澄清及持久恢复；不能用唯一固定工具轨迹判断所有问题。
- **范围 / 数据**：问题/允许权限工具/关键观察/证据/允许事实/终态 schema，分层版本化；复用企业脱敏集但不改名旧 v0.2，不新增未经授权原文。
- **路径 / 交付**：经 M04 确认的 `spec/fixtures/golden-set/**`，M00 schema/矩阵，M11 评测器与报告。
- **计划测试**：`test_FR_AGENT_010_golden_set_agent_paths`、`test_FR_AGENT_010_injection_never_expands_scope`。
- **DoD / 证据**：真实图运行，Fake 仅替换外部模型/服务；证据支持/权限/调用成功/成本耗时统计可复现；Fake 与 live 报告分开。
- **不做**：不合成更多样本冒充企业业务标注，不冻结质量阈值。

### ND-AGENT-05-D live Agent 评测

- **父票 / 来源 / 责任**：ND-AGENT-05；FR-AGENT-010、NFR-QUAL、GATE-P0-004；Accountable M11，Contributors M05/M04/业务/M00。
- **状态 / 依赖**：blocked；05-B/C、ND-P0-01-A 与批准环境。
- **场景 / 异常**：真实模型运行已复核集；人工复核证据覆盖/事实支持/拒答/越权阻断；Judge 仅辅助，成本和耗时不能因重试/恢复漏算。
- **范围 / 数据**：live 图/模型/Prompt/工具/数据集版本、调用/终态/质量/成本/延迟报告；将阈值建议送 ND-P0-04/10，不自行认定通过。
- **路径 / 交付**：`ops/**`、`evidence/` 评测报告与业务复核结论；M00 回填矩阵。
- **计划测试**：`test_FR_AGENT_010_live_evaluation_evidence_complete`、`test_NFR_QUAL_003_citation_support_measured`。
- **DoD / 证据**：报告可回放，偏差/失败与容差显式记录；父票完成不自动关闭 P0 门禁，冻结后按批准阈值重跑。
- **不做**：不以 LLM 自评替代人工，不以完整原文保守门禁通过率宣称语义质量已验收。

## 3. 跨域与人工/环境余量

### ND-GAP-01 后台指标与任务

- **来源 / 责任 / 优先级**：SPEC §5.5、§9.2、NFR-OBS-005/006；P1；Accountable M11，Contributors M00/M06/M07/M10/M03。
- **状态 / 依赖**：blocked；M00 冻结 AdminMetrics/tasks 字段、分页与实现路径 Owner；数字仍 TBD-P0。
- **当前证据**：[PROGRESS](../../PROGRESS.md) 与 [矩阵](../../spec/acceptance/matrix.md) 均记录 `/admin/metrics`、`/admin/tasks` HTTP 未挂；十页 Mock/浏览器存在不等于真实概览。
- **场景 / 范围**：admin 读取真实队列/任务/问答/供应商摘要，普通用户拒绝；接线只读、脱敏、有空/失败状态，禁止在 M11 薄 HTTP 根中堆业务逻辑。
- **路径 / 数据**：先 `progress/changes/`/公共 schema；获批归属后服务端查询端口与 M10 页面消费，不另造任务事实源。
- **计划测试**：`test_FR_RBAC_001_admin_metrics_tasks_forbidden_to_user`、`test_NFR_OBS_005_admin_tasks_read_persisted_facts`。
- **DoD / 证据**：真实响应/分页/负向契约与后台页面集成报告；版本/过滤/错误可追踪。
- **不做**：不更改四页范围，不提前发明指标阈值或公共字段。

### ND-GAP-02 持久审计统一接线

- **来源 / 责任 / 优先级**：FR-AUDIT-001~003、SPEC §2.1/§8.4；P0；Accountable M06，Contributors M03/M01/M02/M05/M11。
- **状态 / 依赖**：blocked；审计 Repository/迁移/权限 Contract 与 Owner 审核。
- **当前证据**：`api/src/pivot/http/bootstrap.py` 装配 `InMemoryAuthAudit`、`MemoryDocumentAudits` 与 `AuditService(AppendOnlyAuditStore())`；[store.py](../../api/src/pivot/audit/store.py) 明确为内存。已有表/追加写单测不等于运行时持久化接线。
- **场景 / 范围**：认证/文档/问答/导出等关键审计写同一 PG 事实接口；进程重启仍可按 request_id/run_id 复盘；普通应用账号不能更新/删除，业务删除不清审计。
- **路径 / 数据**：M06 `audit/**`/sink，M03 SQL/迁移/权限，M11 仅注入；字段脱敏与 ProviderCall 可关联，04-E 负责 Agent 调用对账而非重复实现审计。
- **计划测试**：`test_FR_AUDIT_001_runtime_events_survive_restart`、`test_FR_AUDIT_002_application_role_cannot_update_delete`、`test_FR_AUDIT_003_run_replay_has_provider_versions`。
- **DoD / 证据**：至少 SPEC 关键事件覆盖与真实 PG 账号权限/重启报告；失败写入策略获 Contract 确认；独立备份纳入 ND-P0-08。
- **不做**：不以 Redis/普通日志替代审计，不假定现有导出审计单测已覆盖全部运行时事件。

### ND-GAP-03 密码生命周期验收缺口

- **来源 / 责任 / 优先级**：FR-AUTH-004、FR-AUTH-003；P0；Accountable M01，Contributors M00/M03/M06/M08/M11。
- **状态 / 依赖**：blocked；先确认首次改密/重置机制的 Contract、持久化表达与秘密传递策略。
- **当前证据**：创建/改密/重置 HTTP 已实现；进度仍记 `must_change_password` 不入库、初始密码传递 TBD-P0。此票是差距确认与验收，不据此断言已确认认证漏洞。
- **场景 / 范围**：创建/重置用户后跨实例首次登录、改密、旧 Token 失效与审计；核对是否真实强制完成首次改密，缺项才按批准设计补齐。
- **路径 / 数据**：M01 `auth/**`/`security/**`，M03 仅实现已批持久化需求，M08 消费已发布字段；保留现有 User 枚举/字段直到变更获批。
- **计划测试**：`test_FR_AUTH_004_first_change_required_after_restart`、`test_FR_AUTH_003_reset_revokes_existing_sessions`。
- **DoD / 证据**：明确机制/状态保存来源、跨实例正负向测试、无 URL/日志口令泄漏；若已有证据充分则只补矩阵而不重复实现。
- **不做**：不未经批准新增 `must_change_password` 列，不私定 Token TTL。

### ND-GAP-04 导出下载端到端验收

- **来源 / 责任 / 优先级**：FR-EXPORT-001~003、FR-RBAC-003、SPEC §10.5 第11步；P1；Accountable M06，Contributors M00/M01/M03/M09/M11。
- **状态 / 依赖**：blocked；M00 确认签名 URL 消费者/鉴权/到期机制；04-B 持久答案；TTL 策略。
- **当前证据**：导出任务与对象写入已有；[signer.py](../../api/src/pivot/exports/signer.py) 生成公开签名 URL。当前进度没有实际下载消费者端到端证据，不能把 URL 字符串测试当文件可下载。
- **场景 / 范围**：用户创建导出后实际下载 Markdown/Word；无权限、篡改签名、过期、停用、源资源删除按批准策略拒绝；不包含未校验正文/Prompt/思考链。
- **路径 / 数据**：先公共消费者 Contract；M06 导出服务/签名消费者，M01 重授权，M09 入口，M11 真实对象/浏览器测试；只读 04-B 已持久化事实。
- **计划测试**：`test_FR_EXPORT_001_signed_url_downloads_expected_bytes`、`test_FR_EXPORT_003_expired_or_tampered_download_rejected`、`test_FR_RBAC_003_export_download_reauthorizes`。
- **DoD / 证据**：实际文件/格式、授权、下载/失败/过期审计报告，任务与答案重启后仍可读；缺消费者才按批准兼容方案实现。
- **不做**：不新增破坏性公开对象字节路由，不暴露 MinIO 内部地址，不重跑问答。

### ND-P0-01-A 企业集业务复核

- **父票 / 来源 / 责任**：ND-P0-01；SPEC §10.8、NFR-QUAL；Accountable M11，Contributors 业务/M04/M00。
- **状态 / 依赖**：blocked；Owner 指定业务复核人、准入文档与允许外发边界。
- **场景 / 范围**：复核已存在的 120 条脱敏问句/期望证据/允许答案/拒答标签/版本冲突与 scope；记录有分歧的裁决、标注人和集版本。
- **数据 / 交付**：`spec/fixtures/golden-set/retrieval/**` 经 M04 确认；[ANNOTATION.md](../../spec/fixtures/golden-set/ANNOTATION.md) 与业务复核报告；原文/密钥不提交。
- **计划测试**：`test_NFR_QUAL_enterprise_annotations_have_business_review`；条数/分层/schema 自动校验沿用既有入口。
- **DoD / 证据**：100~150 条且分层符合规范、人工复核签认可追溯；数据集版本与诊断结果分开。真人复核不能由编码会话冒充。
- **不做**：不重建合成集，不把 Fake Keyword 120/120 或脱敏摘录填写当业务验收。

### ND-STG-04-A ECS apply

- **父票 / 来源 / 责任**：ND-STG-04；[dev-staging 范围](../changes/20260910-M00-dev-staging-scope.md)；Accountable M11，Contributors Owner/运维。
- **状态 / 依赖**：blocked；Owner SSH/安全组/磁盘/访问拓扑与批准低敏数据/配置。
- **场景 / 范围**：部署已入库 overlay，固定镜像、迁移、健康/ready 与低敏上传→解析→检索冒烟；只经批准 HTTPS/VPN/SSH 隧道访问，内部存储不公网暴露。
- **数据 / 交付**：现有 `docker-compose.staging.yml`、[runbook](../../ops/runbook-dev-staging.md) 与 apply/失败回滚日志；密钥仅目标环境注入。
- **计划测试**：`test_NFR_OBS_002_staging_dependencies_ready`；部署脚本/配置校验，实际操作日志单列。
- **DoD / 证据**：目标机/版本/数据盘/入口/健康/冒烟/回滚记录，不把未执行操作写成完成；旧 Writer 冒烟不验收 Agent。
- **不做**：不自建 MinerU/模型，不冻结 ECS 生产限额，不因上机关闭 GATE-P0。

## 4. 既有 P0/P1 门禁票的验收补全

以下不重编号、不宣称新票完成；是旧父票下一步的 DoR/测试/证据补全。ND-P0-10 为已有实测结果的汇总发布，不是所有实验的前置依赖，避免与 ND-P0-04/09 相互等待。实验必须显式注入经批准的受控策略，生产默认仍按实测/ADR 冻结。

| 既有票 / Accountable | 当前下一步与硬依赖 | 首批计划测试 / 必须证据 | 状态 |
|---|---|---|---|
| ND-W3-11 / M03（M02贡献） | 先确认上传幂等是否必须以新列或独立持久事实表达；M00/M03 Contract 未批前不加 version.idempotency_key | `test_FR_DOC_005_upload_idempotency_survives_restart`；同键异参、重复消费/提交前后崩溃、迁移报告 | blocked |
| ND-P0-02 / 安全（法务/IT贡献） | 企业文档外发前批准区域/留存/训练/删除政策；staging 例外仅限既批低敏范围，不影响 Agent 每调用外发检查 | `test_FR_AGENT_003_policy_rejects_unapproved_data`；审批记录 + 准入配置来源 | blocked（正式门禁）；staging 范围保留 |
| ND-P0-03 / M04 | 先 live Embedding/rerank opt-in 冒烟；再在复核集上验证真实 dense+BM25+RRF+bge 全链路，不能只测 HTTP 有返回 | `test_FR_RAG_001_live_hybrid_uses_both_routes`、`test_FR_RAG_004_provider_failure_degrades_safely`；Recall/过滤/scope/冲突/代次报告，含 DR-002 对比 | blocked（live 环境/批准配置未确认） |
| ND-P0-04 / M05（算法/业务贡献） | ND-P0-01-A + 02-H + 05 评测；盲评支持校验/数字/否定/条件/版本差异，形成 DR-004 决策 | `test_FR_QA_004_judge_invalid_result_never_answers`；人工优先的模型/阈值/容差报告，冻结后重跑 GATE-P0-004 | blocked |
| ND-P0-05 / M01（业务贡献） | 业务确认仅低敏、全员可见且允许外发的共享库；不满足时走独立 ACL 需求/ADR，不能放宽现有授权 | `test_FR_RBAC_004_unapproved_document_cannot_be_ready`；DR-005 业务准入与管理员会话查看边界签认 | blocked（业务确认） |
| ND-P0-06 / M02（M03/M07/M11贡献） | 可用真实 PG/MinIO/Qdrant/Redis/Celery；W3-11 Contract；非 eager 重复投递、版本切换、删除与孤儿修复 | `test_FR_DOC_006_new_version_publishes_atomically`、`test_FR_DOC_007_delete_hides_before_cleanup`、`test_FR_DOC_008_orphan_scan_is_idempotent`；故障/重启/计数/原子性报告，GATE-P0-003 | blocked |
| ND-P0-07 / M11（M01/M02/M07贡献） | 批准传输/文件限额策略 + GAP-02/03；真实低权限 parser 隔离、受限网络/临时目录、恶意文件与 Secret 扫描 | `test_FR_DOC_003_resource_limits_and_isolation`、`test_NFR_SEC_007_csrf_rejected`、`test_FR_RBAC_003_resource_guessing_forbidden`；HTTPS/Cookie/RBAC/XSS/CORS/压缩炸弹/日志报告，GATE-P0-005 | blocked |
| ND-P0-08 / M11 | 加密 OSS 独立权限 + 新 ECS；备份 PG/MinIO/审计及新增 checkpoint/迁移/图版本/Qdrant snapshot 或重建配置 | `test_NFR_DR_004_restore_to_new_ecs`；用户/Chunk/向量/Citation/审计/抽样问答核对，DR-003 实测 RPO/RTO，GATE-P0-006 | blocked |
| ND-P0-09 / M11 | 真实 ECS/Qdrant/Agent + 批准实验预算；5 并发问答、100k Chunk、1/2/5 解析与上传/导出并行 | `test_NFR_CAP_002_five_concurrent_agent_runs`、`test_NFR_CAP_004_qdrant_100k_peak`；P50/P95/CPU/内存/磁盘/队列峰值，阶段进度与校验后首 Token 分开，GATE-P0-007 | blocked |
| ND-P0-10 / M00（各决策 Owner贡献） | 收集各包实测/审批，分包关闭 TBD，不统一拍默认；范围见下表 | Contract Fixture/配置与 SPEC 对照；来源、Owner、ADR、版本/容差及重跑报告 | blocked |
| ND-P0-11 / M11 | 不可变应用/框架/镜像版本、迁移与发布权限；依赖健康门禁，备份→迁移→启动→冒烟→观察→回滚 | `test_NFR_OBS_002_release_blocks_unready_dependencies`；真实发布/失败回滚/数据兼容/告警演练，GATE-P0-008 | blocked |
| ND-P1-01 / M00（M11贡献） | 八项 GATE-P0 verified + 数据准入/发布契约/TDD Fixture；依赖缺一不可 | `test_GATE_P1_entry_requires_all_p0_evidence`；SPEC §12.3 进入检查报告 | blocked |
| ND-P1-02 / M11（M09/M10贡献） | ND-P1-01、03-E、GAP-01/04；十页真实后端、SPEC §10.5 全14步、安全/性能/可靠性/灾备矩阵 | `test_FR_QA_001_real_stack_end_to_end`；真实上传/搜索/Agent/引用/拒答/单文档/导出/审计/删除/越权浏览器与 API 报告 | blocked |

### 参数冻结包

| 包 / 决策 | Owner | 输入证据 / 对应票 |
|---|---|---|
| Agent 调用数、时间、token/费用、观察/历史窗口、并发、recursion_limit / DR-010 | M05/M11 | 02-B/F、05-D、P0-09；测试 Fixture 不是生产默认 |
| checkpoint/租约保留、删除、加密、恢复、版本兼容 / DR-011 | M03/M01/M11 | 04-A/F、P0-08；保留期需业务/安全确认 |
| Verifier 输入/模型/支持阈值与质量容差 / DR-004 | M05/算法/业务 | P0-01-A、P0-04、05-D |
| 文件大小/页数/Sheet/解压比/时长/空间/批量、原文/导出保留 / DR-008 | M07/M02/M11/业务 | P0-06/07/09；四格式分块 token/overlap/表格定位回归 |
| Dense/BM25/sparse、分词/数字编号、RRF、rerank、距离/模型/维数 / DR-002 | M04/M11 | P0-03、P0-01-A；变化触发新代次/ADR |
| 登录失败阈值/窗口、Token TTL、初始密码传递 | M01/安全 | GAP-03、P0-07；复用现有注入限流，不写死次数 |
| 分页、导出/下载 TTL、SSE 恢复/等待时限、Chrome/Edge 范围 | M00/M06/M08/M11 | 03-A/E、GAP-01/04、P1-02 |
| 资源限额/解析并发、性能/质量阈值、RPO/RTO / DR-003 | M11/相关业务 Owner | P0-03/04/08/09；GATE 与运行配置逐项回写 |

## 5. SPEC 覆盖与不重复开发

| SPEC 范围 | 当前基线 | 剩余票 / 最终验收 |
|---|---|---|
| §0 治理、§5 契约、§12~13 追踪 | contract-v0.1 已发布；新恢复未发布 | 02-A/B/C、03-A、04-A、P0-10、P1-01/02 |
| FR-AUTH-001~004 | 登录/刷新/退出/改密/创建/启停/重置/角色 HTTP 有夹具证据 | GAP-03、P0-07/10；不重建认证服务 |
| FR-RBAC-001~004 | 服务端 RBAC/会话与资源授权已有 | 02-E、03-D、04-C、GAP-01/04、P0-05/07；DR-005 准入仍需业务确认 |
| FR-DOC-001~008、§3.1/§6.1~6.2 | 签名/领域状态/解析 extra/索引/删除有单元或 Fake 证据 | W3-11、P0-06/07/09/10；含四格式/恶意文件/幂等/原子发布/删除/孤儿扫描 |
| FR-SEARCH-001~002、FR-RAG-001~006 | 搜索 HTTP/混合检索端口/HTTP 适配已有 | 02-D/E、P0-01-A/03/10、P1-02；真实两路/过滤/降级/冲突/代次，不以 Fake Keyword 验收 |
| FR-QA-001~006 | 旧线性实现；ND-AGENT-01 门禁子集 done | 02-G/H、03-A~E、04-B、P0-04、05-D |
| FR-STREAM-001~005 | Run/EventLog/SSE 夹具已有 | 02-F、03-B/C/D/E、04-B/D/F；跨进程幂等/取消/重连/累计预算 |
| FR-AGENT-001/002 | 未实现真实图/工具 | 02-A/C/D/G/H；05-C/D |
| FR-AGENT-003/004 | 新上下文/外发与累计预算待实现 | 02-B/E/F、03-D、04-C/E/F |
| FR-AGENT-005/006 | 005 安全子集完成；完整事实/恢复未实现 | 02-H、04-A~F；完整事实/outbox/PG恢复 |
| FR-AGENT-007/008 | 恢复未发布；新轨迹/取消未验收 | 03-A~E、04-D/F |
| FR-AGENT-009/010 | 无 live tools/Agent 评测 | 02-C、05-A~D、P0-01-A/04 |
| FR-EXPORT-001~003、FR-AUDIT-001~003 | 导出任务/对象/短时 URL 有夹具；审计运行时仍内存 | GAP-02/04、04-B/E、P0-07/08、P1-02 |
| NFR-CAP-001~006、NFR-PERF-001~006、NFR-QUAL-001~012 | 初始规模/目标已定，峰值/阈值未验证 | P0-01-A/03/04/09/10、05-D |
| NFR-SEC-001~016 | 领域安全负向/部分 client 已实现；上线验证未完成 | 02-E、GAP-02/03/04、P0-02/05/07/10 |
| NFR-OBS-001~008、§9 | health/ready/Compose fixture 有；真实发布/告警未验收 | GAP-01/02、04-E、STG-04-A、P0-08/09/11（含备份/证书/费用告警） |
| NFR-DR-001~004、NFR-UX-001~005、十页 | 进程内恢复/opt-in 十页不能替代真实环境 | 03-E、GAP-01/04、P0-08/10、P1-02 |
| GATE-P0-001~008 | 全部 unverified | 001→P0-02/05；002→P0-01-A/03；003→P0-06；004→02-H/04/05/P0-04；005→P0-07/GAP-02/03；006→P0-08；007→P0-09；008→P0-11 |
| P1 进入/退出、GATE-P1 索引 | 未满足进入条件 | P1-01/02；GATE-P1 只有索引，不在拆票中编造四项细则 |
| P2/P3 非目标 | deferred | OCR/复杂表格/对比/HITL/Text2SQL/页内高亮/SSO/多机等不在本次实现队列；MinerU staging 不改变 MVP 边界 |

## 6. 每票开工与收尾

1. 读取上位规范、父票、当前 PROGRESS 和相关模块进度；确认 cwd/main 与最新 commit，核对是否存在他人修改。
2. `ready` 前置票先形成 proposed Contract/ADR/Red 设计；实现票必须确认批准版本、依赖与首个可执行 Red，缺任一项仍 blocked。
3. 按 Red → Contract → Green → Refactor → Integration → Regression 推进；测试命名 `test_<requirement_id>_<behavior>()`，外部依赖 Fake/Stub，live opt-in 单独归档。
4. DoD 包括正负向测试、受影响静态检查、场景/矩阵/模块与根进度、精确版本与证据路径；未运行/skip 明确记录，测试名登记不代表通过。
5. 只提交本票路径，格式 `type(Mxx): 中文说明 [票ID, 需求ID]`；跨模块列出路径。不得一并提交用户现有未跟踪原文/密钥或无关源码。
6. 子票完成只关闭本票范围；父票须全部子票及原 DoD 满足，需求 verified 与门禁 verified 分别依据 SPEC 证据，不能自动级联。

下一张票：**ND-AGENT-02-A**（内部模型/工具/State Contract 提案）；随后 02-B/02-C。当前不具备直接实现 02-G 或部署宣称 Agent 可用的条件。

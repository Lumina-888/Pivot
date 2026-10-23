# 变更申请：M05 Agent 上下文瘦身（FR-AGENT-011，M 线）

- **日期**：2026-10-23
- **申请人**：M 线会话（端到端方案第八节，Owner 2026-10-23 批准，排 W 线之后）
- **背景**：Agent 的工作记忆是 `AgentState.messages` 全量重发：每轮 decide 都把此前所有 read_evidence 全文再次发送给模型，历史只受调用预算约束，没有任何淘汰。05-D 实测单场景最高约 12,100 token，且观察到模型重复读取同一证据。依据 Anthropic 上下文工程框架与 JetBrains《The Complexity Trap》的实证结论（确定性观测掩盖的成本约为原始轨迹的一半，完成率与模型摘要持平或略胜，且摘要存在轨迹拉长副作用），本切片只做确定性瘦身，不引入 LLM 摘要、记忆抽取或分层分页。
- **原契约/现状**：
  - decide 把 `state["messages"]` 全量格式化后发送，工具结果原文随历史无限累积。
  - read_evidence 每次调用都返回全文，同一证据可被任意次重复读取并全额计入后续每轮上下文。
  - BudgetPolicy 只有硬上限（调用次数、工具次数、改写次数、总 token 硬顶），没有与上下文瘦身挂钩的软触发点。
- **拟变更内容**（本切片）：
  - M-1 观测掩盖（`agent_graph.decide`）：外发前对格式化消息副本执行 `_mask_read_history`——较早轮次的 read_evidence 全文替换为存根（开头 60 字片段、证据编号与「再次调用 read_evidence 即可重读」提示，并标 `masked`），最近一次读取保留全文。只作用于本次发送的副本，落库状态、检查点与证据注册表保持原文；收尾器从注册表取证据，不受影响。外发门禁检查的正是掩盖后的副本，即模型实际收到的内容。搜索结果与其余消息不处理。
  - M-2 重复读短路（`agent_tools.ReadEvidenceTool`）：图层按 M-1 的掩盖规则判定目标证据的全文是否仍在外发历史中（即它是最近一次全文读取），是则在完成全部既有校验（Run 归属、主体与范围、解析器重授权）之后返回短提示（含 120 字摘要与定位，不带全文字段）；全文已被掩盖的证据再读直接给全文。判据从状态消息推导，不改证据注册表的快照形状，03-A 恢复契约不受影响。该判据是 live 首轮验收后的修正：原设计按读取次数短路（第二次短提示、第三次恢复全文），与掩盖叠加后出现「短提示称全文见前次结果、而前次全文已被掩盖」的自相矛盾，多证据场景的模型为拿回全文反复读取、烧高调用次数；修正后短提示的说法永远为真，纯浪费的重复读（全文就在眼前）才被短路。
  - M-3 预算触发（`agent_budget.BudgetPolicy`）：新增可选字段 `history_token_soft_budget`，默认 None（关）。decide 时若累计已报告 token 达到软预算，掩盖加重为旧读取连开头片段也不留（只剩证据编号与再读提示）；最近一次读取永远保留全文——原设计连最近一次也掩盖会使决策循环看不到刚读到的内容，工具失效，一并在首轮验收后修正。触发信号用供应商已报告的累计用量；供应商不报告用量时不触发（瘦身是成本优化，不是安全门禁，静默不触发可接受）。生产装配本切片不设值，设值即 DR-010 决策。
  - 金标集新增场景 ag-010（stratum `repeat_read`）：同一证据连续读取三次的脚本轨迹，入 Fake 图回归；短提示短路与被掩盖证据再读给全文由 FR-AGENT-011 单测直接断言。
- **影响模块**：M05（agent_graph、agent_tools、agent_budget、Agent Golden Set 夹具）；生产装配（bootstrap）不改，W1 默认预算不设软预算值，行为变化限于：多次读取场景的外发历史构成与第二次读取的返回形状。
- **兼容方案**：单次读取与无重复读取的轨迹外发内容与变更前逐字一致（掩盖只在存在两条以上全文读取时触发，且保留最近一条）。检查点与注册表快照形状不变，旧检查点可正常恢复。短提示是 read_evidence 的新增返回形状，字段为附加式（already_read、excerpt、note），既有消费方（图层与收尾器）不读工具消息正文，不受影响。
- **测试 ID**：`test_FR_AGENT_011_older_reads_are_masked_only_in_outbound_copy`、`test_FR_AGENT_011_repeat_read_of_visible_evidence_returns_stub`、`test_FR_AGENT_011_reread_of_masked_evidence_returns_full_text`、`test_FR_AGENT_011_soft_budget_heavy_masking_strips_excerpts`、`test_FR_AGENT_011_soft_budget_defaults_off`、`test_FR_AGENT_011_soft_budget_must_be_non_negative`；夹具回归 `test_FR_AGENT_010_*`（含 ag-010）。
- **验收**：05-D 装配真实复跑（DeepSeek 官方 deepseek-flash，thinking 开/关两组）通过率不低于基线（两组各 7/9，按原 9 场景口径对账，ag-010 单独报告），多读场景 token 有可测降幅。数据见 `evidence/agent-m05/nd-agent-m-context-slimming.md`。
- **是否触发 ADR**：否。掩盖与短路是既定上下文工程方向内的实现（端到端方案第八节已获 Owner 批准），不改状态机、权限、引用与删除语义；软预算只留开关、不设生产值，数值冻结仍属 DR-010。
- **审核结果**：随 M 线切片提交，待 Owner 随 PR 审核。

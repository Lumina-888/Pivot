# ND-AGENT-02-B：DR-010 预算与累计用量 Contract 提案

- **日期 / 状态**：2026-10-02 / proposed；待消费者及 Owner 签认，不是已发布 Contract、运行许可或 DR-010 关闭记录。
- **提案版本**：AGENT-BUDGET-0.1-draft.2（累计图预算映射修订；仍 proposed）；拟与 [02-A 内部 Contract](20261002-M05-agent-internal-contract.md) 配套，不进入 contract-v0.1 manifest。
- **Accountable / Contributors**：M05；M00/M06/M11，恢复与跨进程预扣接口另需 M03/M01 确认。
- **来源 / 基线**：[SPEC §7.3/§8.3](../../SPEC.md)、[AGENT_SPEC §5~6/§8](../../spec/AGENT_SPEC.md)、[ADR-009](20261002-M00-langgraph-react-baseline.md)；main `715e6d5`，发布 contract-v0.1。
- **工单 / DoR**：[ND-AGENT-02-B](../tickets/spec-1.1-remaining.md) 只允许提案、有限 Fixture 与 Red 设计；02-A 未签认、02-C 未锁依赖，父票及业务实现继续 blocked。

## 1. 目的与实施边界

把工具、模型、基础设施重试、主备切换、补证及未来恢复放在同一 Run 累计账本内。recursion_limit 只保护图调度，不能代替调用、时长、token 或费用门禁。缺必需策略、计量能力或用量上界时 fail closed，不回退线性 RAG。

本轮不修改 `api/`、`worker/`、`web/`、公开 schema/错误码、路由、依赖或迁移，不引入生产默认值。所有新增数值仍为 TBD-P0；下文有限值仅用于提案形状检查和未来 Fake 测试设计。策略语义本身也待签认，不能以本提案代替批准。

旧 [ProviderCallRecorder](../../api/src/pivot/audit/provider.py) / [ProviderCallRecord](../../api/src/pivot/audit/models.py) 仅有 tokens、浮点 estimated_cost、retry_count 和内存记录，不具备预扣/逐 attempt/未知用量/持久对账能力；不能把 `extra` 或缺省零值当作新账本。02-F 实现调用边界；04-A/E 定义持久尝试/账本和对账，不本轮补迁移。

## 2. 必需策略、单位与版本

| 维度 | 拟议计量与边界 | 数值状态 |
|---|---|---|
| model_calls_max | 所有 LLM 的实际派发次数，含 decide/Planner、Finalizer、外部 Verifier、重试及备用；本地纯校验不计模型调用 | TBD-P0 |
| tool_calls_max | search/read 工具执行 attempt；相同 query、合法空观察或失败仍计数 | TBD-P0 |
| run_timeout_ms / step_timeout_ms | Run 总墙钟期限 / 单次调用期限；排队、退避、等待澄清均消耗总时长 | TBD-P0 |
| tokens_max / model_output_tokens_max | 所有有 token 用量的供应商累计输入+输出 / 每次 LLM 的可强制输出上限 | TBD-P0 |
| cost_microunits_max / currency | 单一记账币种，1 microunit = 10^-6 currency unit；上界预扣向上取整，禁止 float/隐式汇率 | TBD-P0 |
| observation_chars_max | 每个完整 ToolMessage.content JSON 的 Unicode code point 数，包含字段名、定位与转义；不是字节或 token | TBD-P0 |
| history_messages_max / history_chars_max | 本 Run 开始时加载的授权业务历史消息数/正文 code point 数，按完整问答组取最近窗口 | TBD-P0 |
| context_tokens_max | 每次模型输入完整请求的 token 上界，含 system/问题/历史/原生调用/观察/工具 schema；不等于历史窗口 | TBD-P0 |
| active_runs_max / principal_active_runs_max | 部署范围/同 principal 同时执行的 Run 槽位；不是累计调用量 | TBD-P0 |
| graph_supersteps_max / recursion_limit | Run 累计图 super-step 上限 / 单次 invoke 技术上限；二者都需显式注入 | TBD-P0 |
| retry_max_attempts / retry_backoff_ms | 每个稳定 action 的总 attempt 上限（含首次/主备），退避表长度为 attempts-1，退避消耗总期限 | TBD-P0 |
| rewrite_max / clarification_max | 初次搜索不计 rewrite，后续 query 改变计一次 / 进入澄清等待最多一次 | 已定：2 / 1 |
| pricing_version / token_counter_version | 各主备/Embedding/Rerank 计价上界及输入 token 计数器版本；Run 固定，恢复不静默换表 | 待能力与策略签认 |

只有明确的策略值才能构造运行策略；`null`、无限值、缺字段、零/负上限、未知版本、无法核实的 approval_ref 不放行。JSON 中出现 approval_ref 仅是引用，不证明有人批准。受控 Fake、批准实验及生产分别核验许可范围；Fixture ID 永不作为生产许可。

### 2.1 拟议 BudgetPolicy 形状

JSON Schema 只保证类型/必填，不保证跨字段关系、许可真实性或供应商能力。没有 default 字段；不能把 schema 的 minimum 当生产默认。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AgentBudgetPolicy",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "policy_id", "approval_ref", "model_calls_max", "tool_calls_max", "run_timeout_ms", "step_timeout_ms", "tokens_max", "model_output_tokens_max", "cost_microunits_max", "currency", "observation_chars_max", "history_messages_max", "history_chars_max", "context_tokens_max", "active_runs_max", "principal_active_runs_max", "graph_supersteps_max", "recursion_limit", "retry_max_attempts", "retry_backoff_ms", "rewrite_max", "clarification_max", "pricing_version", "token_counter_version"],
  "$defs": {
    "positive": {"type": "integer", "minimum": 1},
    "ref": {"type": "string", "pattern": "\\S"}
  },
  "properties": {
    "schema_version": {"const": "budget-policy-0.1-draft.2"},
    "policy_id": {"$ref": "#/$defs/ref"},
    "approval_ref": {"$ref": "#/$defs/ref"},
    "model_calls_max": {"$ref": "#/$defs/positive"},
    "tool_calls_max": {"$ref": "#/$defs/positive"},
    "run_timeout_ms": {"$ref": "#/$defs/positive"},
    "step_timeout_ms": {"$ref": "#/$defs/positive"},
    "tokens_max": {"$ref": "#/$defs/positive"},
    "model_output_tokens_max": {"$ref": "#/$defs/positive"},
    "cost_microunits_max": {"$ref": "#/$defs/positive"},
    "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
    "observation_chars_max": {"$ref": "#/$defs/positive"},
    "history_messages_max": {"$ref": "#/$defs/positive"},
    "history_chars_max": {"$ref": "#/$defs/positive"},
    "context_tokens_max": {"$ref": "#/$defs/positive"},
    "active_runs_max": {"$ref": "#/$defs/positive"},
    "principal_active_runs_max": {"$ref": "#/$defs/positive"},
    "graph_supersteps_max": {"$ref": "#/$defs/positive"},
    "recursion_limit": {"$ref": "#/$defs/positive"},
    "retry_max_attempts": {"$ref": "#/$defs/positive"},
    "retry_backoff_ms": {"type": "array", "items": {"type": "integer", "minimum": 0}},
    "rewrite_max": {"const": 2},
    "clarification_max": {"const": 1},
    "pricing_version": {"$ref": "#/$defs/ref"},
    "token_counter_version": {"$ref": "#/$defs/ref"}
  }
}
```

语义校验另须拒绝 step_timeout_ms > run_timeout_ms、principal_active_runs_max > active_runs_max、recursion_limit > graph_supersteps_max、退避表长度不匹配及无完整消息可装入的策略。context_tokens_max 必须不超过所选模型实际输入容量；输入上界+输出上限还须满足模型总上下文容量、tokens_max 与费用余量。schema 合法而语义不合法的策略不启动 Agent。

## 3. 预扣、派发与结算

### 3.1 Interface 与顺序（拟议，不是现有 Python 定义）

| Interface | 输入 / 输出与责任 |
|---|---|
| BudgetGate.reserve | 可信 run_id、稳定 step/action/attempt、操作/模型版本、输入与输出 token/费用上界；返回 reservation 或内部拒绝分类 |
| BudgetGate.mark_dispatched | 在实际 I/O 前标记尝试；不能证明请求未发送的崩溃窗口按已派发/未知结算处理 |
| BudgetGate.settle | 同一 reservation 的实际用量或显式 unreconciled；幂等应用，不按新事件重复累加 |
| BudgetGate.snapshot / restore | 策略引用/账本 revision/累计及预扣/游标/期限；恢复须对账且不得回滚消费 |
| ExecutionAdmission.acquire / release | 执行前申请部署及 principal 槽位，等待/终态释放；生产原子性、租约/fencing 由 04-A/D 承接 |

先检查身份/owner/scope/取消/最新外发资格，再核预算与取得槽位，登记 attempt 和预扣，才执行调用；返回后先登记用量，再检查取消/授权/资格和下一步。安全拒绝不因此释放已派发调用的费用或许可绕过。图/工具代码不得直接调用未经过此边界的主备 Adapter。

- 每 Run 串行，一个 active action 可含受控的检索子调用；LLM/tool 计数按 §2，Embedding/Rerank 等收费子调用单独登记 provider attempt、预扣 token/费用及适用的 step 期限，不伪装成免费工具。并发检索分支须先预扣全部上界，不能等成功后才补账。
- 总占用 = 已结算计入量 + unreconciled 保守计入量 + 尚未结算 reservation；上界恰好等于剩余额度可派发，超过则不派发。不预留任意隐藏的“最终回答免费额度”；Finalizer/Verifier 也必须申请剩余预算。
- 明确可证明未派发的取消/预检失败可释放 reservation，不增加派发计数；无法证明未派发则消耗 attempt 计数并保留预扣。已派发的超时/429/非法格式/晚到结果不能退回次数，不能默认零 token/费用。
- 输入上界须由锁定计数器对完整请求计量，输出上限须能被 Adapter 强制；费用须覆盖供应商可能计费的所有类别（含 hidden reasoning、固定收费、缓存/失败收费规则）。无法给出有限可靠上界的供应商/操作不可在硬预算模式派发。estimated_cost 是策略估算，不是实际账单或硬计费 exactly-once 保证。
- 报告用量必须有限非负且分类完整；缺失/非法/仅有不完整 totals 或未知计价分类视为 unreconciled。保留预扣上界，不以 0 代替；只有上界仍可信且余量足够才可继续。若上界本身失效，立即停止新的外部调用并送对账。
- 有效实际用量在预扣范围内才可释放差额；实际超过预扣或总预算时记录完整超额（不裁成上限），停止新行动，不发布未验证答案。预算只能阻止下一调用，不能撤销已发生计费。
- 晚到用量可按同一 attempt 对账更新，不能恢复 cancelled/其他终态或重新执行。重复同一结算幂等；同一 attempt 出现相互矛盾的用量则 consistency_invalid，不最后写入覆盖。

### 3.2 拟议用量结算形状

本对象仅为内部 settlement 输入；provider/model/operation/pricing_version 与预扣数值通过 attempt_id 在账本解析。不得用来自模型的 run_id 或任意传入 ID 授权。已派发收费尝试均需此记录，取消/协议非法不免登记。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AgentBudgetSettlement",
  "type": "object",
  "additionalProperties": false,
  "required": ["run_id", "action_id", "attempt_id", "usage_status", "input_tokens", "output_tokens", "estimated_cost_microunits", "currency"],
  "properties": {
    "run_id": {"type": "string", "pattern": "\\S"},
    "action_id": {"type": "string", "pattern": "\\S"},
    "attempt_id": {"type": "string", "pattern": "\\S"},
    "usage_status": {"enum": ["reported", "unreconciled"]},
    "input_tokens": {"type": ["integer", "null"], "minimum": 0},
    "output_tokens": {"type": ["integer", "null"], "minimum": 0},
    "estimated_cost_microunits": {"type": ["integer", "null"], "minimum": 0},
    "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}
  },
  "allOf": [{
    "if": {"properties": {"usage_status": {"const": "reported"}}},
    "then": {"properties": {
      "input_tokens": {"type": "integer"},
      "output_tokens": {"type": "integer"},
      "estimated_cost_microunits": {"type": "integer"}
    }},
    "else": {"properties": {
      "input_tokens": {"type": "null"},
      "output_tokens": {"type": "null"},
      "estimated_cost_microunits": {"type": "null"}
    }}
  }]
}
```

unreconciled 不是“无消费”；完整原始用量片段可以另存脱敏对账记录，但不可拿部分成功字段伪装 reported。只有明确供应商语义证实不收费时 reported 的费用才可为 0；schema 不证明该条件。

## 4. 重写、重试、恢复与期限

- **query 身份**：仅去除首尾空白后逐字比较；不按大小写/标点/语义自动归并。首次实际派发 search 不计 rewrite；之后新 search action 与最近实际派发 search 的 query 不同，则派发前占用一次 rewrite。A→B→A 是两次重写；失败/空结果的已派发 search 也保留 query 与消费。
- **同 query / 重试**：新 action 的同 query 仍计 tool/model 预算；同 action 的基础设施重试/主备 attempt 不重复计 rewrite，但仍计实际调用与用量。稳定 action/attempt 的状态重放不重扣，同一次真实再派发必须登记新的 attempt；不能复用 ID 隐藏重复计费。
- **可重试分类**：仅超时、429、临时 5xx/网络错误。每个 action 的 retry_max_attempts 含首次与主备，不另送备用次数；每次重检策略、主备能力与预算，退避不得超过余下总期限。非法 JSON/工具协议、权限、禁止外发不是可重试故障。
- **澄清**：稳定 clarification action 成功进入 waiting_for_user 时计一次，interrupt 重跑不重复计；第二次拒绝。总期限不暂停、不续期，等待过期不调用模型。公开等待期限/错误映射仍须 03-A；批准前不新增 endpoint 或公开 timeout 字段。
- **deadline**：由服务端首次受理时固定总期限，排队、等待、恢复均不能重置；运行期间使用 monotonic 计时并与可信 UTC deadline 取更小余量，恢复重建计时而不延长 deadline。时钟倒退/期限无法验证 fail closed；生产可信时间/持久期限由 04-A/D 确认。
- **累计图预算**：不同 invoke/None/Command(resume) 共享 Run 累计图账本；`recursion_limit = min(显式技术上限, Run 剩余 super-steps)` **只作技术熔断提示，不是硬上限证明**。候选 LangGraph 1.2.12 的 None 恢复会执行 limit+2 个 tick；不得用减 2、调低默认值或捕获 GraphRecursionError 后补账代替派发前门禁。独立累计计数、重放身份与前置阻断要求见 §4.1；框架读取不扣，实际重执行不免费。02-F/G 未提供安全接缝证据前不得启用业务图。
- **BudgetSnapshot**：保存 policy/pricing/token-counter 版本引用、run 绑定、账本 revision、固定 deadline、model/tool/super-step 消费、tokens/费用的 settled+unreconciled+reserved 分量、query/rewrite/clarification 游标、稳定 attempt/结算状态。checkpoint 不是预算唯一事实；恢复与 attempt 账本对账，较旧快照不覆盖新消费，无法一致则停止。持久协议属 DR-011/04-A/E。
- **并发槽位**：waiting_for_user/终态释放执行槽位，恢复重新申请；累计账本不释放。部署与 principal 槽位需同时原子申请，多进程不能各自给出同一额度。进程内 Fake 只验证 Interface，不证明生产并发门禁/租约。

### 4.1 累计图预算映射审核（draft.2，待消费者签认）

本节替代 draft.1 仅靠 min 映射的充分性假设；不改变生产数值、公开状态或已发布 schema。技术 canary 见 [本轮审核](../../evidence/agent-m03/nd-agent-02-abc-review.md)，**不是 BudgetGate Green**。

| 执行边界 | 必需映射 / 阻断条件 |
|---|---|
| 首次 invoke / ainvoke | 可信 Run 绑定、固定策略与账本 revision；先验证剩余图额度，再打开本次服务端 execution epoch。epoch 不是新预算，也不是客户端 thread_id |
| None / Command 恢复 | 先与最新账本对账；新 epoch 继承全部消费/预扣/deadline。框架本地 step 或恢复后的 recursion_limit 不能清零累计值 |
| 每一实际 super-step | 在该步任何节点体执行前取得累计图许可；成功占用恰好一个图额度。同一步多节点共享该许可，各自模型/工具 attempt 仍独立预扣；禁止通过 fan-out 把两个 I/O 计成一次调用 |
| 中断/异常/崩溃 | 已开始执行的步保留消费，包括 interrupt 前缀、失败步与无法证明未执行的预扣；不可依赖节点返回时更新 state 才记账。checkpoint 未提交不等于没有执行 |
| 读取/重放 | 纯读取、事件重放不消费。仅同一已登记执行的确认/结算幂等；再实际执行必须取得新的许可/attempt，不能复用旧成功 ID 免费执行 |
| 同步/异步/取消竞争 | 使用同一账本规则，取得许可后才进入节点；晚到结果不退款已执行的图/模型/工具消费，不覆盖终态 |
| 余量 0 / 无法验证 step 身份或前置接缝 | 不调用图/节点/I/O，fail closed；不调用“免费 Finalizer”，不切线性 fallback |

**计数身份与原子性**：图许可绑定 `(run_id, execution_epoch, dispatch_step_id)`；标识来自服务端调度边界，不从模型消息、公开 SSE 或未经核验的 checkpoint 推导。许可应在该 super-step 第一个节点体之前原子预扣，其他同一步节点只能验证/使用已取得的许可；下一步及实际重执行必须申请新许可。未知执行窗口保守保留占用；持久预扣/恢复一致性和 fencing 归 04-A/D/E，02-F/G 的单进程 Fake 不能验收生产原子性。

**接缝准入**：02-G 必须证明锁定框架同步/异步、条件分支与恢复均能在执行前识别调度步并阻断，不能只消费 `stream(debug)` 的事后事件或公开日志。若仅有节点入口接缝，须证明图每步只有一个可执行节点、入口先取得许可且无绕过/子图隐藏步骤，或另提保守多节点预扣映射获批准；不得静默把 node 次数当 super-step 次数。无法满足则业务启用 blocked，而不是填一个看似安全的 recursion_limit。

新增/细化计划 Red（均未实施业务测试）：

- `test_FR_AGENT_004_zero_graph_budget_blocks_node_entry`：剩余 0 时节点体、工具、模型调用均为 0；首次/None/Command 与同步/异步分别覆盖。
- `test_FR_AGENT_004_interrupted_prefix_is_charged_before_execution`：interrupt 前缀两次实际进入各有消费；只有 state return 一次不能少记一次。
- `test_FR_AGENT_004_fanout_shares_step_but_not_provider_reservation`：同一步两个节点共享图许可；各 I/O 单独预扣，任一余额不足不得派发。
- `test_FR_AGENT_004_replay_read_does_not_authorize_new_dispatch`：旧快照/同 ID 重放只读不扣，但再次执行需新许可；未提交/未知执行不得退款或免费重放。

消费者签认需同时确认语义、可实现前置接缝与验收边界；技术审核完成不等于已签认实施或 DR-010 accepted。

## 5. 观察、历史与上下文

1. 先过滤/重新授权再构造 Observation；不允许截断操作留下禁止外发的标题/locator/摘要。计量完整 JSON 序列化后的 code points（中文不转 ASCII escape），字段顺序固定；原生调用关联不因截断改变。
2. 丢弃低优先级完整 evidence 项后，按 code point 缩短 excerpt/text 并标 truncated=true；evidence_id/真实 locator/版本等不能截成另一对象。连必需元数据都装不下时，不发送残缺 JSON，按 observation_limit 安全停止。不把 ToolMessage.content 全串切片。
3. 当前工具只返回本 Run 注册证据的有限许可投影；完整 Chunk 留在服务端用于最新授权与 ND-AGENT-01 支持校验。截断观察/缩略定位不能当完整事实支持证明；不能让较短预算导致绕过全量 Claim 验证。
4. 历史仅从已授权、已持久化的业务消息取最近完整问答组，任一资源资格不满足则整组移除；先满足消息数/字符限制，再检查完整模型输入 token 上界。不生成新的 LLM 摘要来暗中增加调用或外发受限衍生文本。
5. 首版不压缩/删除本 Run 原生工具消息或 pending call；上下文超限不产生孤立 ToolMessage，也不静默裁 system/问题/工具 schema。历史完整组可继续从最旧移除，本 Run 必需消息仍超限则停止新模型调用。修复/恢复沿用同一规则，不改变证据注册表。
6. 单步/总期限在返回后也检查；超时、context/observation 限制、recursion 用尽或取消后的模型 content 均不能直接作为正式答案。公开轨迹只发既有白名单脱敏分类，不发内部账本、query、原始 Observation 或用量报文。

## 6. 内部停止分类与发布门禁

以下仅为拟议内部分类，不加入 errors.py/OpenAPI/SSE/Worker error_code；具体公开 HTTP/code 映射归 03-A/B。沿用 SPEC 终态与安全发布不变量，不创造新的公开状态。

| 原因 | 拟议决策 |
|---|---|
| policy_missing / policy_invalid / metering_unavailable | 不派发；请求/执行故障 failed，启动阶段无 Run 则启用失败；不得 fallback |
| budget_exhausted（调用/token/费用/重写） | 无合法证据且无继续路径 refused；有证据但支持不确定 uncertain；不强行调用 Finalizer |
| run_deadline_exceeded / step_timeout | 总期限结束按执行超时 failed；单步可重试仅限仍有累计预算/期限，不退款未知用量 |
| observation_limit / context_limit / graph_limit | 停止行动；证据不足 refused/uncertain；调度异常或计量一致性故障 failed，不视为 answered |
| usage_bound_invalid / consistency_invalid | 保留完整已消费/预扣，停止外部调用并对账；failed，不发布未经验证事实 |
| cancelled / access_denied / egress_denied | 安全停止、不能补证/换供应商绕过；晚到用量仍登记，既有终态不可改写 |

仅当全量支持校验已完成、最新授权/执行资格有效、未取消/未逾总期限且事实提交成功时，才可无额外模型调用地提交/发布已验证答案。不能将“已有证据”“预算恰好耗尽”或“先发 token 再校验”当 answered 条件；完整事务/outbox 由 04-B 验收。

## 7. 有限 Fixture 与预期账本（不是运行许可）

下面是唯一的示例策略，**unit_fake_only / approval pending**；字段 approval_ref 只标明 Fixture 范围，绝非 Owner 签认。不得拷贝进 env/example/生产 fallback。全部数值是人为选择的有限边界，不来源于性能实测。

```json
{
  "fixture_scope": "unit_fake_only",
  "approval_status": "pending",
  "policy": {
    "schema_version": "budget-policy-0.1-draft.2",
    "policy_id": "fixture-budget-01",
    "approval_ref": "fixture-only-not-approved",
    "model_calls_max": 6,
    "tool_calls_max": 6,
    "run_timeout_ms": 12000,
    "step_timeout_ms": 1000,
    "tokens_max": 2000,
    "model_output_tokens_max": 128,
    "cost_microunits_max": 30000,
    "currency": "USD",
    "observation_chars_max": 512,
    "history_messages_max": 4,
    "history_chars_max": 256,
    "context_tokens_max": 1024,
    "active_runs_max": 2,
    "principal_active_runs_max": 1,
    "graph_supersteps_max": 80,
    "recursion_limit": 40,
    "retry_max_attempts": 2,
    "retry_backoff_ms": [25],
    "rewrite_max": 2,
    "clarification_max": 1,
    "pricing_version": "fixture-price-01",
    "token_counter_version": "fixture-counter-01"
  },
  "settlements": [
    {"run_id": "run-fixture", "action_id": "action-1", "attempt_id": "attempt-1", "usage_status": "reported", "input_tokens": 100, "output_tokens": 50, "estimated_cost_microunits": 200, "currency": "USD"},
    {"run_id": "run-fixture", "action_id": "action-2", "attempt_id": "attempt-2", "usage_status": "unreconciled", "input_tokens": null, "output_tokens": null, "estimated_cost_microunits": null, "currency": "USD"},
    {"run_id": "run-fixture", "action_id": "action-2", "attempt_id": "attempt-3", "usage_status": "reported", "input_tokens": 120, "output_tokens": 40, "estimated_cost_microunits": 200, "currency": "USD"}
  ],
  "unreconciled_reservation": {"attempt_id": "attempt-2", "tokens": 500, "cost_microunits": 700},
  "expected_booked": {"model_calls": 3, "tokens": 810, "cost_microunits": 1100},
  "expected_remaining": {"model_calls": 3, "tokens": 1190, "cost_microunits": 28900}
}
```

示例：attempt-1 成功，attempt-2 超时用量未知，attempt-3 是同 action 的备用尝试；只有临时故障、主备能力/上界合法和剩余策略许可时才允许备用。恢复此账本后仍占用 3 次模型、810 tokens 和 1100 microunits，unknown 不归零，重复结算不再加一次。示例算术检查不执行 BudgetGate、恢复或主备逻辑。

Fake 测试可复制策略并仅改变一个有限维度，如 model_calls_max=1、tokens_max=1、run_timeout_ms=1；这是显式测试参数，不作为替代生产默认。FakeClock、受控 blocking Adapter、确定性计数器与 price table 固定种子/版本，无真实密钥、企业文档或供应商 URL。

## 8. 计划 Red / 消费者用例（未实施）

| 计划测试 ID | Given / When | Then / Red 失败判据 | 后续票 |
|---|---|---|---|
| test_FR_AGENT_004_missing_policy_fails_closed | 缺字段、伪造 approval_ref、零/负数或计量版本未知 | 模型/工具派发 0；不走线性 fallback | 02-F/G |
| test_FR_AGENT_004_policy_relations_rejected | shape 合法但单步超总时长/退避长度错/模型上下文装不下 | reserve 拒绝，无供应商调用 | 02-F |
| test_FR_AGENT_004_repeated_query_consumes_budget | 连续同 query 与合法空观察 | rewrite 不增，tool/model 实际 attempt 增，有限终止 | 02-D/F/G |
| test_FR_AGENT_004_rewrite_limit_enforced | search A→B→A→C，或第二次调用基础设施重试 | 两次改变后 C 不派发，重试不重复扣 rewrite | 02-F |
| test_FR_STREAM_005_fallback_does_not_reset_budget | 成功、超时 unknown、备用后恢复 | 按 §7 占用/余量，同 action 两 attempt，主备/恢复不清零 | 02-F、03-D、04-E |
| test_FR_AGENT_004_unknown_usage_retains_reservation | 超时、缺/非法/不完整用量 | unknown 不为 0；无可信上界则无下一调用 | 02-F、04-E |
| test_FR_AGENT_004_reserve_before_dispatch | 余量恰好等上界、超过上界、调用前取消 | 等于可派发，超额不派发；未派发才可释放 | 02-F |
| test_FR_AGENT_004_settlement_is_idempotent | 同 attempt 同结果重放/矛盾用量/超预扣 | 重放不双加；矛盾/超额不裁账、不再调用或发未验证正文 | 02-F、04-E |
| test_FR_STREAM_005_protocol_error_not_retried | 格式/权限/禁止外发失败，已派发有用量 | 不切备用，不退款已消费；无工具越权 | 02-E/F |
| test_FR_AGENT_004_all_provider_roles_share_budget | Planner/Finalizer/Verifier/Embedding/Rerank/收费失败 | 所有收费 attempt 可追踪并预扣；本地纯校验不冒充模型 | 02-F/H、04-E |
| test_FR_AGENT_004_deadline_survives_wait_and_resume | FakeClock 等待/退避/排队/恢复/时钟倒退 | 期限不延长，超时不派发；单步不超余下总期限 | 02-F、03-D、04-C |
| test_FR_AGENT_004_graph_budget_survives_resume | 多次 invoke/interrupt 重跑与递归极限 | 技术/累计双门禁，恢复无免费 super-step | 02-C/G、03-D |
| test_FR_AGENT_004_observation_truncation_preserves_protocol | 中文/emoji/JSON escaping/定位过长 | 完整 JSON 限长，ID/locator 不伪造；无残缺/孤立 ToolMessage | 02-D/F/G |
| test_FR_AGENT_003_history_window_rechecks_egress | 历史问答组禁外发/撤权，窗口满 | 整组移除；无受限摘要外发、无隐藏摘要模型调用 | 02-E/F |
| test_FR_AGENT_004_context_limit_never_drops_pending_call | 工具消息组+schema 超输入容量 | 不裁 pending call/system；无下一模型调用 | 02-F/G |
| test_FR_AGENT_004_concurrency_slots_reacquired_on_resume | 两 principal/同用户争用，等待后恢复 | 部署与用户双约束，无累计消费释放；Fake 不验收跨进程 | 02-F、03-D、04-D/F |
| test_FR_QA_004_repair_requires_budget | verify 不通过且预算耗尽/总期限到期 | 不补证、不派 Finalizer；无未验证 token/消息/导出 | 02-H、03-C、04-B |
| test_FR_AGENT_004_budget_survives_resume | checkpoint 比 attempt 账本旧或不同策略/Run | 不回滚预算/混 Run，不静默换策略；无法对账失败 | 03-D、04-C/E/F |

Schema/示例算术检查不能把这些行为测试标 passed；真实图、interrupt、PG、多进程与 live 必须分别提供后续证据。

## 9. 实验、审批与兼容

| 阶段 | 允许的证据 / 依赖 | 放行边界 |
|---|---|---|
| 本轮提案 | shape 正负例、有限 Fixture 算术/版本/链接、旧契约回归 | 不运行新 Agent，不关闭 DR-010 |
| 批准后的 Fake | 02-A/B/C 签认；02-D~H 真实图 + Fake 模型/基础设施 | 仅显式 unit 策略；不能转生产配置 |
| 受控性能/能力实验 | Owner 书面批准样本、主备模型、token/金额/并发总额度、环境与停止条件 | 逐维度改变上限，采实际尝试/unknown/成本/时长/context 峰值；无许可则 blocked |
| 生产冻结 | M05/M11 实测报告与业务/运维/Owner 审核、DR-010 accepted、更新 SPEC/Contract/Fixture | 才可发布生产策略；框架/恢复/DR-011 各自独立放行 |

实验计划覆盖同 query 循环、不同 Observation、多轮读证据、Verifier 补证、超时/429/主备、等待恢复、最长许可历史/观察与注入；先单 Run 再在 NFR-CAP-002 已定不超过 5 在线并发内采峰值。5 不是本提案默认 active_runs_max，100k/ECS 验收仍归后续 P0 票。报告记录 Python/框架/模型/工具/Prompt/数据/计价/计数器版本、失败/unknown、P50/P95与峰值、累计真实费用和估算偏差；指标阈值仍 TBD-P0。

**兼容 / ADR**：本提案是 DR-010 候选决策，未 accepted；不覆盖 ADR-009、安全支持策略或公开状态。contract-v0.1/旧线性回归不变，不新增 env/default、错误枚举或客户可填的预算/thread 参数。公开恢复/错误/等待策略归 03-A；事实/租约/对账归 04-A/E；若签认改变状态/权限/引用或模型配置，必须另按 SPEC §0.6 登记，不以本提案隐式发布。

| 消费者 / 审批人 | 待确认事项 | 状态 |
|---|---|---|
| M00 | 内部版本、停止分类与公开映射隔离、受控/生产发布门禁 | pending；无签认 |
| M05 | 全角色调用/预扣/结算、重写/重试/期限与真实图预算 | pending；提案作者不等于批准 |
| M06 | 非 float 计价、未知用量/attempt 对账、ProviderCall 兼容 | pending；无签认 |
| M11 | Fixture 边界、计量/性能实验、主备上界验证与证据 | pending；无签认 |
| M03 | snapshot 对账/原子预扣/并发、04-A/E 持久协议承接 | pending；无签认 |
| M01 | 恢复授权/历史外发重检、principal 并发不信模型参数 | pending；无签认 |
| Owner / 业务 / 运维 | 明确受控运行许可、成本与期限语义；生产数值实测批准 | pending；无签认 |

### 9.1 2026-10-02 签认跟进

主线会话完成技术自审：draft.1 的 min 映射不能充当硬门禁，按 §4.1 修订为 draft.2；预扣/未知用量/所有模型角色与 graph/provider 双计量无绕过要求保留。审核记录及待签清单见 [02-A/B/C 审核](../../evidence/agent-m03/nd-agent-02-abc-review.md)。**这不是消费者或 Owner 代签**；上表 pending 不变。运行时 Red 仍未实施，生产数值与受控运行许可均未批准。

## 10. 本轮结论与下一步

02-B 进入 review（proposed 提案与 Red 设计已提交，**非 done**）；有限 Fixture 形状与算术检查只验证文档 artifact。完整验证与限制见 [nd-agent-02-b.md](../../evidence/agent-m05/nd-agent-02-b.md)。02-A/B 消费者及 Owner 均待签认；默认下一刀 02-C Python 3.12 依赖验证/锁定申请。02-D~H/父票继续 blocked，DR-010/011、恢复契约、TBD-P0 与全部 GATE 未关闭。

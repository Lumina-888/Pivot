# ND-AGENT-02-A：模型、工具与状态内部 Contract 提案

- **日期 / 状态**：2026-10-02 / proposed；设计提交待审核，不是已发布契约或业务实现。
- **提案版本**：AGENT-INTERNAL-0.1-draft.1；只适用于待实现的新 Agent，不进入 contract-v0.1 manifest。
- **Accountable / Contributors**：M05；M00/M01/M03/M04/M06/M11。
- **来源**：[SPEC §4.5/§7/§8.3](../../SPEC.md)、[AGENT_SPEC §3~5/§7/§10](../../spec/AGENT_SPEC.md)、[ADR-009](20261002-M00-langgraph-react-baseline.md)。
- **工单 / 原基线**：[ND-AGENT-02-A](../tickets/spec-1.1-remaining.md)；main `cdadc53`，发布 contract-v0.1，ND-AGENT-01 安全基线 `8cd4727`。
- **DoR 边界**：只允许提案与 Red 用例设计；02-B/DR-010、02-C 锁依赖和消费者签认未满足，02 父票与业务实现仍 blocked。

## 1. 背景与范围

旧 [QA 端口](../../api/src/pivot/qa/ports.py) 只有 Retriever/DraftWriter/Verifier，不支持原生模型工具往返。EvidenceHit 缺检索与 Embedding 版本、代次、版本冲突和完整文档策略；[检索模型](../../api/src/pivot/retrieval/models.py) 有部分追踪信息，但 [装配桥接](../../api/src/pivot/http/bootstrap.py) 会丢掉这些字段，也未传真实 locator。不能用旧 hits 自动填空字段来宣称新证据 Contract 满足。

本提案定义一个受控决策 Interface：模型选择行动，服务端负责执行资格与发布。沿用现有混合检索和答案安全策略，不增加另一套检索、认证或支持性算法。

本轮不修改 `api/`、`worker/`、`web/`、依赖、迁移或公共 schema；不安装 LangGraph、不添加恢复 endpoint、不改变 HTTP/SSE 状态或错误枚举，不冻结任何 TBD-P0。未审核的机器形状只放在本提案内，不生成生产客户端。

## 2. Interface 与调用顺序

下表是拟议 Interface，不是现有 Python 定义；异步方式、LangChain 类型与依赖版本在 02-C 确认后落地。

| Interface | 输入 | 输出 / 责任 |
|---|---|---|
| AgentModel.capabilities | 服务端选择的模型配置引用 | 下文能力声明；主备分别验收，声明不能代替受控能力测试 |
| AgentModel.decide | 已授权的 model_messages、两个工具 schema、调用上下文 | 原生 AIMessage、实际用量或明确未知用量、供应商完成分类；不返回正式答案 |
| ToolExecutor.execute | 一个经验证的 tool_call + 可信 RunContext | 一个同 ID 的 ToolMessage + 仅服务端 EvidenceRegistry 增量 |
| StructuredFinalizer.finalize | 问题、获准的 evidence_id/正文、调用上下文 | 严格 Claims JSON + 用量；不接受自由 Markdown、模型定位或 Citation ID |
| EvidenceResolver.resolve | 服务端 principal/scope、已登记的文档/版本/Chunk/代次引用 | 最新授权与完整正文/真实定位/版本信息；不依赖旧 Observation 授权 |
| ResultPublisher.publish | 全量支持校验通过的结果 + 最新执行资格 | 幂等业务事实提交；事务/outbox/租约 Interface 由 04-A/B 定义 |

每次调用都经过：可信身份/owner/scope 与取消检查 → 最新文档和外发策略检查 → 02-B 预算预检/尝试登记 → 实际调用 → 用量登记 → 再检查取消与资源资格。晚到结果不能直接写答案。供应商 endpoint/key/连接对象只由服务端 Adapter 持有，不作为模型参数或输出。

合法原生工具调用 → ToolGuard → 工具 → ObservationGuard → 原 tool_call_id 的 ToolMessage → 下一次 decide。无工具调用 → 严格控制意图 → finalize/clarify/refuse；finalize 仍须独立 Finalizer/Verifier/Publisher。工具响应内嵌的指令、JSON 或控制意图都只是数据。

## 3. 模型能力与消息协议

### 3.1 能力声明（草案）

启用新 Agent 时主备都须明确支持原生 tool calling、关联 ID、结构化输出和调用超时。无法真正取消远端调用时声明 `cancel_mode=boundary_only`，记录残余计费风险，返回后仍重检取消。用量允许显式 unknown，但不能记作零；unknown 的预算处理依赖 02-B，未批准不能放行调用。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AgentModelCapabilities",
  "type": "object",
  "additionalProperties": false,
  "required": ["native_tool_calls", "tool_call_ids", "structured_output", "timeout_control", "cancel_mode", "usage_mode"],
  "properties": {
    "native_tool_calls": {"const": true},
    "tool_call_ids": {"const": true},
    "structured_output": {"const": true},
    "timeout_control": {"const": true},
    "cancel_mode": {"enum": ["cooperative", "boundary_only"]},
    "usage_mode": {"enum": ["reported", "explicit_unknown"]}
  }
}
```

### 3.2 单工具模型回合（草案）

以下是 **Adapter 规范化后的原生调用投影**，不接受模型在自由文本中伪造这个对象。Adapter 从 AIMessage.tool_calls 读取 `id/name/args`，拒绝 invalid_tool_calls、解析失败或缺 ID；不得补造供应商缺失的 tool_call_id。message_id/step_id/attempt_id 由服务端稳定分配，与供应商工具 ID 分开。供应商 arguments JSON 禁止重复键、NaN/Infinity，解码后再执行 schema 和非空白字符串校验。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AgentToolTurn",
  "type": "object",
  "additionalProperties": false,
  "required": ["tool_calls"],
  "properties": {
    "tool_calls": {
      "type": "array", "minItems": 1, "maxItems": 1,
      "items": {
        "oneOf": [
          {
            "type": "object", "additionalProperties": false,
            "required": ["id", "name", "args"],
            "properties": {
              "id": {"type": "string", "pattern": "\\S"},
              "name": {"const": "search_knowledge"},
              "args": {
                "type": "object", "additionalProperties": false,
                "required": ["query"],
                "properties": {"query": {"type": "string", "pattern": "\\S"}}
              }
            }
          },
          {
            "type": "object", "additionalProperties": false,
            "required": ["id", "name", "args"],
            "properties": {
              "id": {"type": "string", "pattern": "\\S"},
              "name": {"const": "read_evidence"},
              "args": {
                "type": "object", "additionalProperties": false,
                "required": ["evidence_id"],
                "properties": {"evidence_id": {"type": "string", "pattern": "\\S"}}
              }
            }
          }
        ]
      }
    }
  }
}
```

- 每回合恰好一个调用；多个调用整回合失败，不选择第一个、不隐式并行。
- 主动文本 content 不成为正式答案；工具回合中不解析其控制意图。若 Adapter 另行识别出独立结构化控制意图与工具调用并存，则拒绝混合协议。
- 工具 schema 给模型的参数仅为 `query` 或 `evidence_id`；principal/scope/URL/路径/SQL/检索或模型配置均拒绝。
- 一个成功执行的调用必须追加恰好一个 ToolMessage，tool_call_id 与原 id 逐字一致，然后才能再次调用模型。不匹配、孤立或重复工具消息为内部协议错误。
- 同一 Run 不允许后续模型回合复用已使用的调用 ID；同一已登记 action 的崩溃重放按原身份对账，而非新执行。具体稳定 action/attempt 与恢复一致性由 02-B/04-A 冻结。
- 当取消、权限或外发禁止发生时停止路径，不把这类错误作为可继续的 Observation，也不转备用供应商；未配对 pending call 只能保留在停止/恢复状态，不能发送下一次模型请求。

### 3.3 无工具调用的控制意图（草案）

只对 tool_calls 为空且无 invalid_tool_calls 的 AIMessage.content 解码 **一个完整 JSON 对象**，不接受 Markdown fence、前后解释、自由答案或 Thought/Action 正则。refuse/clarify 的文本仍为不可信候选，经专用脱敏与状态门禁处理，不能夹带未验证企业事实；02-A 不定义公开澄清 payload。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AgentControlIntent",
  "oneOf": [
    {
      "type": "object", "additionalProperties": false,
      "required": ["intent"],
      "properties": {"intent": {"const": "finalize"}}
    },
    {
      "type": "object", "additionalProperties": false,
      "required": ["intent", "question"],
      "properties": {
        "intent": {"const": "clarify"},
        "question": {"type": "string", "pattern": "\\S"}
      }
    },
    {
      "type": "object", "additionalProperties": false,
      "required": ["intent", "reason"],
      "properties": {
        "intent": {"const": "refuse"},
        "reason": {"enum": ["insufficient_evidence", "unresolved_conflict"]}
      }
    }
  ]
}
```

`finalize` 不是 answered；无合法证据时不得调用 Finalizer。澄清最多一轮，等待/恢复 Contract 在 03-A/D；模型的 refuse 不能替代服务端对执行故障、安全拒绝或预算耗尽的终态判断。

## 4. Observation 与 EvidenceRegistry

### 4.1 工具 Observation（拟议字段，不是公开 SSE）

| 字段 | 约束 |
|---|---|
| status | ok / insufficient / failed；合法空搜索为 insufficient，不是假装供应商失败 |
| evidence | ok 时非空；search 项为 evidence_id、限长 excerpt、许可 locator/版本元数据；read 项为同一 evidence_id、限长 text 和许可元数据 |
| truncated | 明确观察是否被截断；观察长度/计量单位与截断规则由 02-B 冻结，无批准策略不能发送 |
| failure_category | 仅 failed 时出现，白名单脱敏分类；无堆栈、endpoint、key、内部对象路径或原始错误文本 |
| conflict_refs | 本 Run 已登记证据之间的冲突引用及允许展示的版本/生效区间，不由模型自行造版本 |

search 结果可以只含外发许可子集；被过滤资源不暴露标识、数量或正文。read 的未知/其他 Run ID 与已失效 ID 使用同一不泄露存在性的拒绝结果；不带正文。版本/权限/外发改变后旧 Observation 必须作废，不能继续拿它作答案依据。

正文、摘要、标题、locator、历史及所有衍生元数据分别经过同一策略检查；不是只检查 external_llm_allowed 布尔值。合法观察作为不可信 ToolMessage.content JSON 数据发送，不提升为 system/developer 指令；不得把原始 Observation 投影到普通 SSE 或日志。

### 4.2 注册表条目（拟议服务端记录）

| 字段组 | 必需内容 / 不变量 |
|---|---|
| 归属与句柄 | run_id、服务端生成的不透明 evidence_id；绑定当前 Run，不用内容 hash 作为跨 Run 可猜测句柄 |
| 事实引用 | document_id、version_id、chunk_id、真实 locator、text_hash；locator 不支持时明确标注不可用，不伪造页码 |
| 配置追踪 | index_generation、embedding_model_version、retrieval_config_version；缺失时 Contract 不满足，不静默填空字符串 |
| 版本元数据 | version_label、生效区间与冲突关联；来自事实源，不能从模型文本推断 |
| 来源列表 | 稳定 action_id/step_id、原 tool_call_id、来源工具、授权检查时点；相同证据重复命中保留全部来源 |
| 数据策略 | 服务端取得的 classification/external_llm_allowed 等资格快照及检查时点；快照只作审计，不作未来授权 |

按 `(document_id, version_id, chunk_id, index_generation)` 在本 Run 内去重；不同版本/代次不合并。相同身份内容 hash 或真实定位不一致是事实一致性错误，不用后一次覆盖前一次。新检索不能悄悄换 Run 固定的配置版本；重建/切换策略留给独立 Contract。

注册前由服务端从 M04 结果与 M03 事实源补齐/核实资格和定位，不把工具给出的任意 ID 直接写入注册表。历史 Citation 只是一条解析线索，必须重新授权/读取/登记才能取得本 Run evidence_id。每次 read、模型调用与最终发布前重新核实；失效后不得通过另一条工具或旧消息绕过。

## 5. RunContext 与 AgentState 分界

### 5.1 可信 RunContext（运行时注入，不序列化）

run_id/conversation_id、当前 active principal、会话 owner/有效 scope、检索/事实读取/模型 Adapter 句柄、外发策略、02-B 必需预算策略、取消/时钟/执行资格句柄。来自服务端认证与业务事实；客户端/model/thread_id/旧 checkpoint 都不是授权依据。

RunContext 和状态绑定引用不一致时失败，不能覆盖 state 以扩大范围。恢复必须重新构造 RunContext 并复核 active/owner/scope/资源/预算，不能沿用存储时的身份快照。

### 5.2 可序列化 AgentState（拟议字段组）

| 字段组 | 序列化边界 |
|---|---|
| state_version / version_refs | 本提案版本、graph/Prompt/tool/model/检索/Embedding/代次引用；未知或不兼容版本拒绝，迁移策略由 04-A/C 批准 |
| run_binding | Run/Conversation/owner 与有效 scope 的绑定引用，用于恢复一致性检查，不授权 |
| messages | 必需的 human/assistant/tool 内容、message_id、合法 tool_calls、关联 tool_call_id；白名单序列化，不原样存供应商 additional_kwargs |
| observations / evidence_registry | 已授权的敏感观察、注册表、有效性标记与来源；可保存正文但受 DR-011 治理，不是普通日志 |
| pending_action / cursor | 最多一个待处理工具调用、稳定 step/action/attempt 引用及执行游标；完成记录防孤立/重复消息 |
| budget_snapshot | 已消费用量与策略版本的序列化快照；具体维度/未知用量/预扣结算由 02-B 冻结，不添加零值默认 |
| rewrite_count / clarification_count | 首次 search 不计 rewrite，后续查询改变计一次，rewrite≤2、clarification≤1；恢复/主备切换不清零 |
| candidate / verification_feedback | Finalizer 草稿和校验分类/失效证据引用；仅内部敏感状态，不可直接公开 |

禁止进入 state/checkpoint：API key、Bearer/refresh token、数据库密码、供应商 endpoint/存储内部路径、连接/依赖对象、取消句柄、完整系统 Prompt、供应商私有 reasoning/Thought。graph thread_id 由服务端映射一 Run 一 thread，不能接受客户端自选。Prompt 以版本引用恢复；业务用户文本与授权证据仍属敏感数据，不因为 JSON 可序列化而可公开。

本轮只定义数据责任与不变量，不冻结 Checkpointer 表、加密/保留/备份/迁移/租约数值；这些由 04-A/DR-011 决定。不能用通用 dataclass/asdict 或原始框架 dump 绕过白名单。

## 6. Finalizer 与答案校验 Interface

独立 Finalizer 只接收本 Run 合法、最新授权且允许外发的 evidence_id/正文。内部严格输出如下；模型不生成 Claim/Citation 业务 ID、页码、support 或 confidence，也没有第二份 markdown 字段。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AgentFinalizerOutput",
  "type": "object",
  "additionalProperties": false,
  "required": ["claims"],
  "properties": {
    "claims": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["text", "evidence_ids"],
        "properties": {
          "text": {"type": "string", "pattern": "\\S"},
          "evidence_ids": {
            "type": "array", "minItems": 1, "uniqueItems": true,
            "items": {"type": "string", "pattern": "\\S"}
          }
        }
      }
    }
  }
}
```

Schema 只保证形状，不能证明句子被支持、ID 属于当前 Run、文档仍可用或没有注入。服务端为每个 Claim 解析 evidence_ids、重新核实候选/版本/授权/外发，生成真实 Citation 与绑定，执行全量支持门禁。沿用 ND-AGENT-01 完整 Chunk 原文保守策略，不能用截断 Observation 的片段作完整支持证明；语义 Judge 替代仍须 DR-004。

任一 Claim/ID/绑定/支持/Verifier 结果非法则整份不发布。Verifier 不得改写事实；合法补证且有预算才给 Agent 安全分类反馈，格式/权限/外发禁止不走模型自动修复或主备重试。只有 verified Claims 渲染正文；完整事务/outbox/取消竞争在 04-B/D 验收。clarify/refuse 与 failed 的公开说明由服务端固定模板投影，不直接显示模型自由文本。

## 7. 内部失败分类（草案，非新增公共错误码）

| 分类 | 例子 | 拟议处理 |
|---|---|---|
| capability_missing / policy_missing | 不支持 tools、必需预算策略缺失 | Agent 模式 fail closed，不静默切旧线性模式 |
| model_protocol_invalid | 多调用、未知工具、额外参数、缺 ID、非法 JSON、混合控制协议 | 无工具执行；登记失败尝试/用量，不作基础设施重试或切备用 |
| message_protocol_invalid | ID 不匹配、孤立/重复 ToolMessage | 不调用下一模型，不发布结果 |
| evidence_unavailable | 未知/其他 Run/失效 evidence_id | 同一脱敏结果、不泄露存在性；资源拒绝不得靠循环绕过 |
| access_denied / egress_denied / cancelled | 用户/owner/scope/数据策略变化、取消 | 立即停止相关路径；晚到结果不发布，不切工具/供应商 |
| provider_transient | 超时、429、临时 5xx、临时网络故障 | 仅在共享累计预算与策略许可下有限重试/主备切换 |
| observation_insufficient | 合法空观察 | 新行动可选；消耗工具/模型预算及必要的 rewrite，不视为临时故障 |
| verification_inconclusive | 有合法证据但不能证明支持 | 预算内合法补证，否则 uncertain/refused；Verifier 故障绝不通过 |
| consistency_invalid | 元数据缺失、同一事实身份内容冲突 | fail closed，不伪造追踪信息或 locator |

失败分类只是内部决策输入，不是模型可选择的权限指令。公开 HTTP/SSE code/state 与新类别的映射由 03-A/B 经 M00 确认；不得把这些字符串加入当前 errors.py/OpenAPI/Worker error_code 枚举。

## 8. Fake 消费者与 Red 设计（未执行业务测试）

以下用例检验 **未来运行时 Interface**。它们没有因本提案通过文档检查而 passed；所有 Fake 只替换模型/基础设施，真实图由 02-G 验收。测试实现必须先确认消费者 Contract，并按 Red → Contract → Green 开工。

| 计划测试 ID | Given / When | Then / Red 失败判据 | 消费者 / 后续票 |
|---|---|---|---|
| test_FR_AGENT_002_extra_tool_arguments_rejected | search args 加 principal_id/scope/URL；read 加 chunk_id | 拒绝整回合，检索/读取 Fake 调用次数 0，不能接受宽松 kwargs | M05/M01；02-D/E |
| test_FR_AGENT_001_tool_message_matches_call_id | Fake AIMessage 原生调用 id=c1；工具给 id=c2 | 匹配时下一模型看到同 ID ToolMessage；错配时无下一模型调用 | M05；02-G |
| test_FR_AGENT_009_tool_capability_required | 主或备用 Adapter 不支持 tools/结构化输出 | 启动/请求失败；线性 Orchestrator 未调用 | M05/M11；02-C/G |
| test_FR_AGENT_002_multiple_calls_fail_closed | 同响应带 search 与 read 两调用 | 两个工具都未执行，不取首个/不并行/不重试 | M05；02-D/G |
| test_FR_STREAM_005_protocol_error_not_retried | 无 ID、重复调用 ID、invalid_tool_calls 或非法控制 JSON | 不调用备用模型；失败尝试与已消费用量不被清零 | M05/M06；02-F/G |
| test_FR_AGENT_002_foreign_run_evidence_rejected | Run B 用 Run A 或猜测 evidence_id | 无正文/存在性差异；读取 Fake 无未授权调用 | M01/M05；02-D/E |
| test_FR_AGENT_002_registry_keeps_version_and_sources | 同 Chunk 重复命中、同文档不同版本/代次 | 本 Run 去重保留两来源；不同版本不合并；真实定位/版本完整 | M04/M05；02-D |
| test_FR_AGENT_003_restricted_history_never_sent | 删除/禁外发证据及其旧摘要/历史准备外部调用 | Planner/Finalizer/Verifier/主备均不接收受限内容 | M01/M05；02-E |
| test_FR_AGENT_001_observation_drives_next_tool | 搜索分别返回合法空与足够证据 | Fake 模型分别改写或 read/finalize；真实图动作随观察改变，非固定两次搜索 | M05/M11；02-G |
| test_FR_AGENT_005_unverified_markdown_never_published | Finalizer 带自由 markdown、未知 ID 或百万美元奖金 Claim | 未验证内容不进入正文/消息/导出；任一 Claim 不通过整份拒绝 | M05/M06；02-H |
| test_FR_AGENT_006_checkpoint_has_no_credentials | runtime context 含 Secret/依赖/私有 reasoning | 白名单 state 序列化不含它们；不把本例当真实 PG checkpoint 验收 | M03/M01；04-A/C |

## 9. 影响、兼容与待签认

- **兼容**：contract-v0.1 和既有 Retriever/DraftWriter/Verifier 暂时不变；未来新 Agent Interface 单独引入。仅对模型参数 schema 严格限制，不借机扩大权限或改变公开引用/删除语义。
- **ADR**：细化 ADR-009 已批准目标与不变量，不新增架构裁决；DR-010/011 和 DR-004 均未关闭。若审核改变权限、支持/引用/删除或模型配置，须另行 ADR，不能据本提案直接实现。
- **发布条件**：所有受影响消费者确认 Interface、错误与兼容策略，02-B 预算/用量和 02-C 消息类型/锁依赖完成，M00 确认后方可发布 `spec/contracts/` 内部版本；不隐式提高父票状态。

| 消费者 | 必须确认的事项 | 本轮状态 |
|---|---|---|
| M00 | 内部版本/严格 shape 与公开错误映射隔离、后续发布路径 | pending；无签认 |
| M01 | RunContext 重建、历史/观察/全部模型角色外发门禁 | pending；无签认 |
| M03 | EvidenceResolver 事实字段、state 白名单/版本；依赖与持久化另案 | pending；无签认 |
| M04 | 检索追踪/冲突字段无损传递与真实定位来源 | pending；无签认 |
| M05 | 单调用/控制意图/消息关联、Finalizer 与旧安全门禁兼容 | pending；提案作者不等于已批准 |
| M06 | ProviderCall 尝试/用量、结果发布/导出消费责任 | pending；无签认 |
| M11 | Fake 消费者与后续真实图/live 验收区分 | pending；无签认 |

## 10. 验证与下一步

本轮只校验提案 JSON schema/正负形状示例、本地 Markdown 链接与既有公共契约/QA 回归；实际命令、版本、结果和工作区限制见 [本轮证据](../../evidence/agent-m05/nd-agent-02-a.md)。JSON Schema 不验证 ID 往返、外发、支持性、预算或恢复行为。

02-A 进入 review（proposed 待签认），**不是 done**。下一刀可开始 02-B/DR-010 提案与受控 Fixture 设计，随后 02-C 依赖验证/申请；02-D~H 与父票继续 blocked。没有新增公开接口、生产运行参数或 ReAct/GATE 验收声明。

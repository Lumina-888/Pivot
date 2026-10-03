# ND-AGENT-03-A 澄清恢复公开 Contract 提案

| 项目 | 内容 |
|---|---|
| 版本 / 日期 | AGENT-RESUME-0.1-draft.1 / 2026-10-03 |
| 状态 | proposed；03-A review 待签认，未发布、不是可调用 API |
| Accountable | M00；Contributors M01/M03/M05/M08/M09，M11 记录回归证据 |
| 来源 | [SPEC §3.2/§5.4](../../SPEC.md)、[AGENT_SPEC §8.3/§9](../../spec/AGENT_SPEC.md)、[03-A 工单](../tickets/spec-1.1-remaining.md#nd-agent-03-a-恢复公开契约) |
| 原契约 | contract-v0.1；[OpenAPI](../../spec/contracts/openapi.yaml) 不含 resume |
| 拟议 schema | [agent-resume.schema.json](../../spec/contracts/proposals/agent-resume.schema.json)，独立 proposed 目录，不加入发布基线 |
| 证据 | [nd-agent-03-a.md](../../evidence/agent-m00/nd-agent-03-a.md) |

## 1. 背景与实施边界

03-A 可独立编写提案；02-A/B/C、DR-010、02 闭环和消费者审核未满足，禁止恢复业务实现/生产客户端。schema 检查不是授权、幂等或真实图验收。本刀不改 SPEC、公开 OpenAPI/SSE/Worker、业务错误枚举、路由、依赖、迁移或生产配置。

本提案细化 ADR-009 已接受的一轮澄清、waiting_for_user → resuming → retrieving、同 Run/预算不重置与服务端授权，不改变既有状态机或权限。新增公开字段/错误含义均待 M00/消费者/Owner 批准；如批准时偏离上述不变量，须另登记 ADR。DR-010/011 不关闭。

## 2. 拟议 HTTP 与等待视图

### 2.1 回复请求

仅拟议 `POST /api/v1/runs/{id}/resume`，Bearer access token；不是匿名链接，Cookie/CSRF 规则沿用批准的认证方案。请求为 `application/json`：

```json
{
  "clarification_id": "clarify_001",
  "answer": "使用现行制度。",
  "idempotency_key": "resume_001"
}
```

- `id` 为已有 Run；服务端生成不可猜测的 `clarification_id`，绑定该 Run 的唯一一次有效 interrupt，不能用它绕过 owner 鉴权。
- 三字段必需，必须为非空白字符串；严格拒绝额外字段。ID 长度沿用 contract-v0.1 的 128 上限，不设新生产阈值。
- `answer` 是不可信用户数据，不是工具指令；不接收文件、URL 执行请求、客户端身份/scope/thread/checkpoint/预算或任意 Command。
- 只使用 body 幂等键，与现有 CreateRunRequest 的风格一致；不定义第二个 Idempotency-Key header 通道。
- 拒绝重复 JSON 键、非对象、非法 JSON、非 string/coercion；schema 只验证 JSON 解码后的形状，重复键/解码行为属于后续 HTTP Red。
- answer/prompt 字符或字节限额、等待期限、幂等记录保留策略仍 TBD-P0。未来启用恢复时缺必需批准策略 fail closed，不能将 schema 未设 maxLength 理解为允许无限请求。

### 2.2 等待信息

拟议在 `GET /runs/{id}` 的 RunDetail 增加可选 `clarification`：只有 `waiting_for_user` 且当前用户合法可见时返回下面对象，其他状态省略。旧字段不变；目前已发布 RunDetail 是 additionalProperties=false，**发布时必须同步升级它和消费者**，不是现在向 v0.1 偷加字段。

```json
{
  "clarification_id": "clarify_001",
  "prompt": "请确认要查询哪个制度版本？"
}
```

prompt 经服务端验证、长度限制与安全公开投影；不能包含原始 reasoning/Prompt/工具参数、受保护证据或存在性线索。不能直接公开 LangGraph interrupt value。确认等待信息持久可读后再允许 waiting_for_user 阶段事件入 outbox。

SSE 不新增事件、payload 或 state；只用现有 stage 信封通知 `waiting_for_user`，客户端通过 GET 读取等待视图，连接丢失/重连不会提交 resume。waiting_for_user 不是终态，不发布 token/citation/completed。等待阶段的连接生命周期由既有 SSE 策略和后续 03-B/E 确认，不在本刀冻结。

### 2.3 受理回执

首次受理和同键同参重放均拟议 HTTP **202**：

```json
{
  "run_id": "run_001",
  "message_id": "msg_001",
  "clarification_id": "clarify_001",
  "state": "resuming",
  "request_id": "req_001"
}
```

`state=resuming` 是持久受理回执的历史状态，不是响应时刻最新状态；客户端 GET/SSE 获取实际 retrieving/终态。run_id/message_id 保持原值，不创建新 Run、助手 Message 或重置原问题/scope；澄清回复作为本 Run 敏感恢复输入保存，其业务 Message 表达由 04-A 冻结，不私设 sender 枚举。

同键重放沿用持久 receipt 的业务字段，本次 request_id 新生成用于追踪；原 admission request_id 留在审计中，不向调用者暴露内部记录。回执不含答案/证据、attempt/thread/租约、调用用量或供应商信息。

## 3. 鉴权、幂等与竞争顺序

1. 验证 Bearer、active/token_version；加载 Run/Conversation，重新校验 owner 与会话未删除。管理员没有代替 owner 回复的隐式例外。不存在、不可见、他人 Run 均统一404，不先返回 state 或 clarification 信息。
2. 在授权之后严格解析/校验 JSON 和已批准大小策略。不因422向非 owner 泄露资源存在性；语法/请求体读取的前置传输限制不得泄露业务内容。
3. 查询幂等受理记录：命名空间 `(principal_id, run_id, operation=resume, idempotency_key)`，与创建 Run 的键空间隔离。绑定解码后的 `(clarification_id, answer)` 精确值；不 trim、Unicode 归一化或改变大小写。可以用固定字段/顺序的结构化序列化摘要作索引，但需比较绑定值或提供等价无歧义证明，不能拼接字符串。摘要/answer 不进公开日志。
4. 已成功受理的同键同参请求，在最新鉴权通过后重放202，**即使当前 Run 已进入终态**；不执行 Command、不追加用户输入、不重扣预算或重复业务事件。旧鉴权快照不可授权重放。同键异参409 IDEMPOTENCY_CONFLICT。未成功受理的校验/临时失败不占据成功键；提交结果不明确时原键重试并查询事实，禁止换键新开 Run。
5. 新键须 state=waiting_for_user、clarification_id 等于当前有效 ID、澄清次数为1且该等待尚未消费；第二轮 interrupt 禁止。重新检查 scope、文档/外发资格、固定图/State/模型版本、checkpoint 可恢复性与累计预算/原期限，不信任 checkpoint 权限快照。
6. 受理事务原子记录唯一回复/幂等映射、条件转移 waiting_for_user → resuming 和可重放执行意图。每 `(run_id, clarification_id)` 最多一个有效受理；不同键并发即使 answer 相同，也只有一个受理，失败者409 RESUME_NOT_ALLOWED。同键竞争只返回同一 receipt。事务失败不返回202。
7. 取消、等待超时或另一有效认领先提交，则新回复不得提交/调图。已受理后取消仍可获胜；执行者在模型/工具/提交边界重检 cancelled/租约/fencing，晚到结果不能覆盖终态。HTTP 返回202不保证外部调用一定启动。
8. 执行入口消费唯一受理意图，重建可信上下文，用服务端 thread 与 Command(resume=answer) 恢复同一 Run。预算、已消耗 rewrite/clarification 次数、截止时间和调用尝试不重置。interrupt 前缀可重跑，不放入非幂等审计/计费/写操作。

生产持久受理/执行意图、租约/fencing/outbox、敏感输入保留/加密与版本兼容均由 04-A/B/D 冻结，不能由本提案决定表结构或用 BackgroundTasks/进程内 set 保证。03-D 的 InMemorySaver 只能证明开发夹具行为。这里的单次受理/结果发布不承诺供应商 exactly-once 计费。

预算耗尽、资源删除/外发撤销且无合法继续路径：按 SPEC/02-B 安全终止原 Run（failed/refused/uncertain，不能发布未验证正文），新请求409 RESUME_NOT_ALLOWED；不泄露是哪份证据被删除/受限。成功回执重放只是查询已受理事实，不重新授予已撤销资源的使用权。

## 4. 拟议错误映射

所有 body 保持 SPEC §5.1 的 `code/message/request_id/details/retryable`；details 固定空对象，不返回 Pydantic 输入、堆栈、owner、checkpoint、Prompt 或证据。message 为固定脱敏文案，不嵌入用户 answer。

| HTTP | code | retryable | 触发条件 |
|---|---|---|---|
| 401 | AUTH_INVALID_CREDENTIALS | false | 缺失/无效/过期凭证；复用当前认证映射，语义签认待 M01 |
| 403 | AUTH_FORBIDDEN | false | active/token_version 认证后的账户禁用/拒绝 |
| 404 | RESOURCE_NOT_FOUND | false | 不存在/不可见/非 owner/会话删除，同文案且不返回 state |
| 409 | IDEMPOTENCY_CONFLICT | false | 当前授权键绑定的 answer/clarification_id 不同 |
| 409 | RESUME_NOT_ALLOWED（拟新增） | false | 新键错误状态、已消费等待、第二轮、无法合法继续/配置不足 |
| 409 | CLARIFICATION_MISMATCH（拟新增） | false | 合法 owner 对尚可受理等待提交过期/他 Run 的澄清 ID，不泄露来源 |
| 409 | RUN_CANCELLED | false | 尚无该键成功回执且取消已提交 |
| 409 | RUN_TIMEOUT | false | 尚无该键成功回执且批准等待/Run 总期限已耗尽 |
| 422 | INVALID_RESUME_REQUEST（拟新增） | false | 已鉴权 owner 的非法 JSON/字段/大小/重复 JSON 键 |
| 503 | PROVIDER_TEMPORARY_ERROR | true | 受理事实存储/执行意图持久化临时不可用，按原键重试；不自动重跑模型 |

[拟议 schema](../../spec/contracts/proposals/agent-resume.schema.json) 的 ResumeFailure 是测试用 `(http_status, body)` 配对，**线上 body 不新增 http_status 字段**。ResumeError 定义信封形状，只有与 ResumeFailure 映射组合后才是完整错误契约。

新错误名和现有错误在 resume 场景中的语义/HTTP 映射只是 proposed，不写 `api/src/pivot/errors.py` 或公开 Error 枚举；批准时必须经 M00 更新 SPEC 附录 B 与新契约版本。错误竞争优先级为鉴权/不可见 → 已受理键重放或冲突 → 新键终态/时限 → 状态/澄清ID → 其他恢复门禁；不借重试绕过拒绝。

## 5. 兼容与发布门禁

- 拟议发布为兼容扩展 contract-v0.2/API `/api/v1`；03-A 提案版本不是发布版本。新路由、RunDetail 可选字段、新错误枚举仍需严格旧消费者的升级窗口/能力协商，不能因字段 optional 就认定旧客户端必然可用。
- 发布前确认 M08/M09 可解析扩展、拒绝未知 state/error 时可安全降级；旧客户端不可启用会产生澄清的 Agent 模式，保持既有已批准行为或明确不可用，不静默 fallback 线性 RAG。
- 不改变 existing RunCreated.initial_state 的 TBD、旧 Run/EventLog 事实或 SSE 信封/事件集合。本刀不更新 manifest/version/CHANGELOG 伪装发布，也不生成 SDK。
- 02 闭环、02-A/B/C/DR-010 签认、下表消费者全部确认后重核 DoR，再走发布。生产恢复另依赖 04/DR-011，不能先通过内存测试宣称可恢复。

## 6. 测试与待实施消费者用例

已实施测试仅为 [拟议 schema 检查](../../tests/contract/test_contract_agent_resume_proposal.py)：请求/回执/等待视图、严格字段和类型、10组错误配对及负向、proposal 未进入公开 OpenAPI。不是下面的运行时证据。

| 计划测试 ID | Given / When / Then；失败判据 |
|---|---|
| test_FR_AGENT_007_resume_contract_owner_required | 无凭证/停用/非 owner/不存在 Run；请求回复；401/403/统一404，不暴露 state/澄清，不调图 |
| test_FR_AGENT_007_resume_idempotency_conflict | 已受理键；改变 answer 或澄清ID；409，不新增执行/输入/事件 |
| test_FR_AGENT_007_duplicate_resume_single_execution | 同键并发/超时后重试；一次受理、稳定 run/message/receipt，本次 request_id，Command 至多有效执行一次；真实崩溃由04-F覆盖 |
| test_FR_AGENT_007_new_key_cannot_repeat_clarification | 两个不同键竞争或等待已消费；一方202、另一方409；无第二轮 |
| test_FR_AGENT_007_resume_receipt_replay_after_terminal | 先受理后 answered/cancelled；同键同参重放202历史回执，GET当前终态，不再调用模型 |
| test_FR_AGENT_007_resume_rechecks_authorization | 受理后用户停用/会话删除；同键重放仍拒绝，不泄露 receipt |
| test_FR_AGENT_004_budget_survives_resume | 等待期间消耗/期限；恢复后不重置预算，余额不足安全结束 |
| test_FR_AGENT_007_resume_rechecks_resources | 删除/外发撤销/scope改变/图版本不匹配；恢复时 fail closed，不能用旧证据或换供应商绕过 |
| test_FR_AGENT_008_cancel_blocks_late_resume | 回复与取消/等待超时竞争；条件事务和提交边界保护，终态不可覆盖 |
| test_FR_AGENT_007_invalid_resume_json_is_redacted | 重复键、未知字段/伪造thread/scope、空白、类型coercion/超限；422空details，无敏感输入反射 |
| test_FR_AGENT_007_web_resume_same_run | GET等待视图→原键回复→GET/SSE；无新Run/重复Message，重连不回复，澄清ID重放不重复渲染 |
| test_FR_AGENT_006_resume_admission_survives_crash | 事务前/后崩溃/派发失败；未提交不202，已提交可查意图/回执，重启不重复公开发布（04-A/F） |

schema 能证明字段白名单，不能证明 active/owner、不同参数幂等冲突、状态条件、预算/取消/lease 或脱敏 prompt。不得把形状检查命名为运行时授权/幂等测试后宣称通过；上述登记测试均待各实施票。

## 7. 待签认清单与开放决策

| 消费者 / Owner | 必须确认 | 状态 |
|---|---|---|
| M00 / 规格治理 | 公开 endpoint/可选视图/回执、错误映射、SPEC 附录同步与版本/升级窗口 | pending |
| M01 / 安全 | owner-only、不可见404、停用/重放鉴权、输入/外发与敏感prompt规则 | pending |
| M03 | 单次受理/幂等命名空间、条件事务、执行意图与04-A/DR-011边界 | pending |
| M05 | interrupt ID/原thread、状态/回执分离、累计预算/取消、错误优先级 | pending |
| M08 / M09 | GET等待视图、原键重试、202历史回执、错误与SSE消费、旧客户端兼容 | pending |
| M11 | HTTP负向/真实图/并发崩溃/浏览器验收分层与证据 | pending |
| Owner / 业务安全 | 等待/输入限额/幂等保留策略的批准来源与运行范围；不得拍生产默认 | pending |

作者自审和 schema/旧回归通过不代替签认。所有 pending 项保留；03-A 状态 review，不是 done；03 父票和03-B~E/04实现继续 blocked。独立下一前置为04-A proposed；关键路径仍先02-A/B/C签认和目标平台锁验证。

# ND-AGENT-04-A checkpoint、租约、事实与 outbox Contract 提案

| 项目 | 内容 |
|---|---|
| 版本 / 日期 | AGENT-PERSISTENCE-0.1-draft.1 / 2026-10-03 |
| 状态 | proposed；04-A review 待签认，未发布、未实施迁移；DR-011 未关闭 |
| Accountable | M03；Contributors M00/M01/M05/M06/M11 |
| 来源 | [SPEC §2/§3.2/§3.3/§7.3](../../SPEC.md)、[AGENT_SPEC §5/§8/§9](../../spec/AGENT_SPEC.md)、[04-A 工单](../tickets/spec-1.1-remaining.md#nd-agent-04-a-dr-011-与迁移契约) |
| 原基线 | contract-v0.1；SQL Run/EventLog 兼容存储，无 checkpoint/租约/outbox |
| 拟议 schema | [agent-persistence.schema.json](../../spec/contracts/proposals/agent-persistence.schema.json)，内部元数据白名单，不是 SQL DDL 或 AgentState schema |
| 证据 | [nd-agent-04-a.md](../../evidence/agent-m03/nd-agent-04-a.md) |

## 1. 范围与 ADR 边界

本刀只提交 DR-011 的设计候选和迁移申请，不关闭决策、不修改 SPEC/正式契约/业务源码/依赖/迁移/CI/配置。状态、权限、整份答案校验和取消语义沿用 ADR-009；下列数据库对象、事务协议与敏感治理均须消费者/Owner 审核后作为 DR-011 决策发布。如审核改变已有状态机、删除或引用语义，另登记批准 ADR，不以本稿隐式生效。

前置 [02-A 内部状态](20261002-M05-agent-internal-contract.md)、[02-B draft.2 预算](20261002-M05-agent-budget-contract.md)、[02-C 依赖](20261002-M03-agent-dependencies-lock.md)、[03-A 恢复](20261003-M00-agent-resume-contract.md) 均 proposed/review。发布本契约和04-B~F实施仍需03闭环、依赖/治理签认和受控真实PG环境。框架候选版本不是本稿批准的生产版本。

形状测试边界沿用04-A工单：只验证内部 LeaseToken、CheckpointBinding、ResultCommitReceipt、OutboxRecord、ProviderAttempt、GovernancePolicy 的必填/类型/白名单。不能据此验证数据库竞争、实际状态脱敏、预算、崩溃恢复或供应商计费。

## 2. 当前代码差距

- [conversations.py](../../api/src/pivot/db/models/conversations.py) 已有 Run/Message/Claim/Citation 表，但 Run 无 state_version/thread/version bundle，AgentEvent 无 `(run_id, seq)` 唯一约束；Citation.claim_id 可空，缺少同 Run/真实版本与 Chunk 一致性约束。
- [runs.py](../../api/src/pivot/db/runs.py) `save()` 无条件更新状态，`_replace_events()` 删除再插入全部日志；仅写合成 Message，未把 Claims/Citation 同事务写入。不能扩用该接口承担 Agent 并发发布。
- [operations.py](../../api/src/pivot/db/models/operations.py) ProviderCall 为聚合元数据，浮点 estimated_cost/总 tokens 不能表达逐 action/attempt 预扣和未知用量。
- Conversation 删除及 ORM cascade 会删除部分执行事实；必须按本稿治理分离隐藏、终止、物理清理。现有旧路径本刀不改，不把存在表/SQLite绿灯当新恢复验收。

## 3. 拟议持久对象与约束

以下是逻辑对象名，物理表名/索引/迁移号需04-B/C实施前核对真实PG Saver锁版本。ID沿用不透明String(128)；各键由服务端生成，客户端不得填写thread/lease/version/budget。

| 对象 | 字段/关系与必须由数据库保证的约束 |
|---|---|
| RunExecution | `run_id`一对一Run；服务端`thread_id UNIQUE`，固定 graph/state/prompt/tools/model/依赖锁/budget policy版本、原`deadline_at`；`state_version >= 0`单调；引用当前兼容checkpoint/ledger游标；不保存凭证或依赖句柄 |
| ExecutionLease | `run_id PRIMARY KEY`，executor_id、fencing_token、expires_at；每次新认领单调递增token，释放/取消不删除计数行；状态版本独立于token；只有一个有效持有者 |
| ResultCommit | `run_id UNIQUE`、result_id、message_id、terminal_state、验证版本/证据快照标识；绑定Run原助手Message，禁止新造第二份答案；answered要求所有Claim已支持且绑定本Run引用 |
| Claim / Citation | 复用既有事实表；新增同Run关联约束及版本/Chunk归属校验，不只检查ID存在；同Chunk支持多个Claim时各自绑定真实Citation；支持正文/locator原样可追溯，公开/导出再授权 |
| PublicEventOutbox | event_id主键，`(run_id, seq) UNIQUE`、`(run_id, publication_key) UNIQUE`；事件名、既有SSE信封、安全投影版本；每Run终态partial unique；事件内容/seq/timestamp提交后不可改写 |
| ResumeAdmission | 03-A命名空间`(principal_id, run_id, operation, idempotency_key) UNIQUE`；`(run_id, clarification_id) UNIQUE`；敏感精确answer/绑定摘要、历史receipt、一次恢复执行意图；不另造公开sender枚举 |
| ExecutionIntent | run_id/action_id、create或resume意图、消费/认领状态；事务入库，Redis只通知；扫描可补发，不能仅依赖HTTP BackgroundTasks或parse队列 |
| ProviderAttempt / BudgetLedger | `(run_id, action_id, attempt_id) UNIQUE`；稳定action、每次实际派发的新attempt、reservation、fencing、角色/模型版本、request_id、派发状态、reported/unreconciled用量、计价/币种；预扣与结算幂等，主备/恢复累计 |
| CheckpointBinding | run_id/thread/checkpoint id、写入fencing/状态版本、execution_epoch、固定版本组、budget_ledger_version；敏感State/框架表独立权限；历史checkpoint不可覆盖已更新绑定 |

租约和原期限都使用数据库UTC时钟，不采信执行者本地钟。恢复不能清零fencing、Run attempt、用量或预算。时间比较、版本相等、seq连续、跨对象FK及条件更新不由JSON Schema证明。

## 4. 租约、checkpoint 与重放协议

### 4.1 认领与 fencing

1. PG事务锁定RunExecution/Run/Lease（所有写路径固定同一锁顺序）；检查非终态、批准期限、执行意图、配置/兼容性；仅不存在持有者或已到期可认领。token原子递增，签发LeaseToken；renew同executor/token且未过期，不能复活旧token。
2. 续期/阶段状态/预算预扣/证据登记/恢复受理/结果提交/事件追加必须在同一事务边界重检当前token、未过期和预期state_version。CAS失败整个事务回滚，不执行外部调用或发布。取消是获授权的独立控制事务，不要求旧执行者token；条件转终态并递增state_version，撤销租约，使晚到提交失效。
3. waiting_for_user在可恢复checkpoint确认后提交一次等待事实/安全stage和澄清ID；释放在线并发槽和租约但保留所有累计预算/原期限。resume重新认领更高token，不复用旧executor权限。
4. 已终态的同result/action重放只读查询已提交回执；不得为了返回回执重新写事实/续租。HTTP/SSE重新鉴权；既有幂等成功回执与新键错误行为遵循03-A，不绕过取消。

### 4.2 框架 Saver 不自动提供 fencing

仅在节点入口检查LeaseToken不够：进程暂停后租约过期，旧Saver仍可能写checkpoint。拟议实现必须使用受fencing保护的Saver适配器，对`put`、`put_writes`及绑定更新在PG事务内锁定并检查Run/Lease；**任何会改变待恢复状态的框架写操作均不能绕开它**。固定锁版本真实测试须证明同步/异步/pool调用全部覆盖，原生Saver不能直接供Runner调用。

框架checkpoint与业务事实可以分事务，不能假设默认Saver共享应用Session；框架表和业务表需在可协调同一PG事实域。敏感State先按02-A白名单正规化、移除reasoning/凭证后加密，授权角色再写；serde自身不脱敏。框架公开接口不足以实现上述写入保护时04-C blocked，另提隔离namespace/适配方案并签认，不能降低为节点前检查。

checkpoint成功后才条件更新可恢复CheckpointBinding。恢复仅使用绑定指向的已确认checkpoint及兼容版本；忽略未绑定孤儿写，保守保留其调用reservation。旧fencing checkpoint只能作为经新认领者验证的恢复起点，不能赋予旧执行者写权限。

恢复先读PG终态/已提交结果：终态只回放业务事件，不调用图。非终态重建active/owner/scope/文档资格/外发策略；固定版本缺失或不兼容fail closed，不静默换图/工具/模型或fallback线性RAG。保留累计ledger、rewrite/clarification、原期限；checkpoint预算落后时以持久账本保守对账，不恢复旧余额。`execution_epoch`在获准的新图调用前递增，稳定action映射避免interrupt前缀重复有效副作用，不能依赖框架tick计数实现02-B硬预算。

## 5. 答案事实事务、事件与取消

`commit_result(LeaseToken, expected_state_version, stable result_id, verified_candidate)`拟议新UoW，不复用旧无条件save。应用从可信上下文取得Run及候选，原Markdown不进入可信输入。

1. 固定锁顺序读取Run/Lease和结果幂等键；已提交相同result且候选绑定一致只返回原receipt，使用结构化规范编码/摘要与必要精确比较判定相等（不把文本拼接当指纹）；同result异候选是内部冲突，不能返回成功掩盖差异或改写已终态。对新的提交重检token/期限/版本和非终态。
2. 最新active/owner/scope/文档tombstone/current/期限/外发及证据归属重新校验；所有Claim支持关系通过，不以候选合法代替支持证明。文档删除/版本切换与结果事务使用可串行化锁/CAS规则（实施前由M02/M04确认资源版本接口）；不能先读资格后不加保护提交。
3. 同事务写Claims、Citation绑定、原助手Message最终受控渲染、Run终态/完成时间、ResultCommit、安全审计/ProviderCall关联及outbox。answered任一Claim失败全回滚；refused/uncertain/failed/cancelled不携带未验证候选正文/Citation。
4. 锁定每Run事件计数器分配seq，使用稳定publication_key；token/citation/completed序列随已验证事实一起提交，terminal最后且至多一个，终态后禁止追加业务事件。任意写失败不发布任何正文/回执，旧答案不能被半更新。
5. 提交成功后dispatcher读outbox，不调用图。AgentEvent兼容读取可以投影同一不可变记录，不能再delete/replace。网络发送至少一次，SSE断线可重复同event/seq；dispatch标记仅诊断，不阻止授权重连重放。不承诺网络exactly-once。
6. 取消与结果锁同一Run：取消先提交则结果CAS失败；结果先提交则取消幂等读终态，不改答案。dispatcher按Run seq顺序读取；订阅和重连执行最新授权，不能因outbox已存就向失效用户推送受限正文。

原问题/助手Message id沿用Run，不从checkpoint重建正式答案。澄清answer拟保存为敏感ResumeAdmission输入，暂不新建Message sender/额外助手答案；是否展示用户回复需M00/M05/M08另确认公开视图，不在本刀改API。导出/会话消息仅读已提交业务事实，且继续执行资源授权。

## 6. ProviderCall 与预算崩溃窗口

模型/工具/Finalizer/Verifier的稳定action跨恢复不变；真正重新派发必须新attempt（保留相同action和关联原attempt），不能用旧attempt掩盖第二次调用。主备分别固定模型/政策并按02-B单独预扣。

- 派发前在受fencing保护事务内持久reservation及ProviderAttempt，随后登记`dispatching`再调用。仅可证明未派发才释放；dispatching后崩溃/超时/用量缺失统一unreconciled，不能默认为0。
- 返回后在事务中幂等结算，实际input/output tokens和estimated_cost_microunits使用02-B单位，整数微币单位/显式币种/计价版本；零用量必须有reported依据，估算不是供应商账单。
- 旧executor的晚到响应不可写图/公开结果；可通过独立M06受审计对账入口，校验原attempt身份和reservation后仅补用量，不续租、不改Run终态、不能减账低于可信实耗。该入口不得接受任意客户端用量。
- 供应商明确支持幂等/结果查询时使用稳定供应商键并确认其保存期、错误/主备语义；不支持时unknown尝试默认不盲目重发，只有02-B批准的剩余预算/有限重试策略许可才新attempt，并记录可能重复计费。checkpoint不提供外部exactly-once。

## 7. 故障窗口与计划 Red

下列运行时测试均未实施；对应04-B~F，不以shape通过替代。

| 计划测试 | 故障点 / 必须结果 |
|---|---|
| test_FR_AGENT_006_fencing_rejects_stale_executor | A暂停、B到期接管；A的事实/预算/阶段/checkpoint put和put_writes全部拒绝 |
| test_FR_AGENT_006_only_one_executor_per_run | 两真实进程竞争认领/续期，只有一个有效token；Redis通知丢失仍可扫描意图 |
| test_FR_AGENT_006_restart_from_checkpoint | checkpoint已写/未绑定分别崩溃；只能从已确认版本恢复，孤儿不授权、用量不回退 |
| test_FR_AGENT_006_checkpoint_has_no_credentials | 嵌套消息/工具/provider私有reasoning canary及依赖句柄；实际序列化前拒绝或白名单移除，框架写/备份/日志无泄漏 |
| test_FR_AGENT_006_restore_rechecks_authorization | 用户停用、会话隐藏、资源删除或外发撤销；不发模型请求/受限事件，旧快照不授权 |
| test_FR_AGENT_004_persisted_budget_survives_restart | graph已执行、checkpoint未提交/interrupt前缀重跑；ledger/epoch/原期限保守累计，不重复扣相同有效动作、不漏新attempt |
| test_FR_QA_002_result_transaction_rolls_back | 任一Claim/Citation/Message/终态/outbox写失败；零公开正文，旧事实不变 |
| test_FR_STREAM_002_outbox_replay_preserves_seq | 提交后发送前/后崩溃；稳定seq/内容、唯一终态，重连重复网络帧不产生新业务记录 |
| test_FR_AGENT_008_cancel_blocks_late_answer | 取消与提交真实PG事务竞争；一终态、无晚到答案/导出覆盖 |
| test_FR_AGENT_007_duplicate_resume_single_execution | 受理前/后崩溃、同键/不同键并发；单次输入/意图/receipt，原Run/thread/预算不变 |
| test_FR_AUDIT_003_provider_attempt_survives_restart | dispatching后崩溃/返回后未结算；unknown保留预扣，reported幂等，晚到只对账不改终态 |
| test_FR_AGENT_006_version_mismatch_fails_closed | graph/state/prompt/tools/model/锁版本不匹配；无静默升级/图执行/线性fallback |
| test_NFR_DR_004_agent_backup_restore | 新环境恢复加密checkpoint/事实/outbox/尝试/版本/密钥访问；终态回放不调模型、已清理数据不复活 |

## 8. 敏感治理与必需策略

Checkpoint是敏感执行状态，不是普通日志。GovernancePolicy只描述必需策略引用及正整数期限，测试显式注入`unit_fake_only`夹具。生产保留期/租约时长/续期间隔/备份保留与密钥轮换均TBD-P0；缺经批准策略/密钥/权限时Agent持久模式fail closed，不从schema或example提供默认。策略加载时另验证续期间隔小于租约时长且满足批准安全余量，tombstone覆盖可重放/备份/幂等记录的最长生命周期，清理与密钥保留不能使仍需恢复的状态不可读；schema只检查独立字段的正整数，不证明这些跨字段条件或approval_ref真实获批。

- State按02-A字段白名单和正文来源授权处理；禁key/URL凭证、连接对象、系统凭证、供应商reasoning和未批准遥测。metadata schema禁止额外字段，但不证明真实嵌套AgentState已安全序列化。
- 传输与PG/备份存储加密；checkpoint敏感payload使用批准密钥服务支持的加密适配/密钥版本，应用源码/DB/日志不得保存原key。metadata key_ref只是标识，不是密钥。Saver读取须重建授权，SSE/debug不暴露thread/checkpoint。
- 独立最小权限角色：迁移账号建表，Runner访问指定Run的执行状态，dispatcher只读安全outbox，M06对账仅更新允许的尝试用量；普通应用账号不能任意读取checkpoint或修改/删除审计。数据库角色/行隔离真实PG负向测试后才可验收。
- 用户会话隐藏先禁止新执行/恢复/读取，撤销意图/租约并安全终止活跃Run；文档tombstone立即阻止证据复用。随后按批准策略清理checkpoint/框架blobs/writes、ResumeAdmission敏感输入及派生缓存；业务Citation保留/失效展示遵循SPEC资源授权，不在此私删事实。
- 不沿用ORM级cascade清掉审计或未知用量账本。必须保留非敏感幂等/取消/fencing tombstone以防旧任务复活；其保留期限和删除顺序亦待Owner确认，清理器幂等/受审计。
- 加密OSS备份包括PG业务/checkpoint/outbox/ledger/审计、批准密钥恢复方式及所有固定代码/依赖/图版本。恢复先重放删除清单并阻止旧executor（重建无效租约、推进token），不得自动重发所有unknown ProviderCall。RPO/RTO仍待新环境演练。

## 9. 迁移与回滚候选

1. 审核锁版本/真实Saver DDL及权限、容量；不在运行时自动`setup()`建表。M03独立批准迁移身份执行框架迁移，记录版本/checksum与应用Alembic依赖顺序，先备份并验证可恢复。
2. Expand新增执行/租约/ledger/receipt/outbox/受理对象与索引；既有Claim/Citation约束先扫描孤儿/错Run/重复seq。发现差距fail closed/隔离并提供报告，不能自动删数据修索引。
3. 旧Run标记legacy不可恢复，不伪造checkpoint/预算/新版验收；仅在证据完整时导入旧已终态事件，保留原seq和字节语义，不重跑模型。旧非终态的收尾策略须M05/Owner单独确认，不自动套Agent版本。
4. 新Agent opt-in使用新事务路径；旧save/EventLog保留独立兼容基线，禁止同Run混用。完成真实PG前进/回滚、角色权限和故障矩阵后再启用；正式依赖/CI/镜像变更另走02-C。
5. 回滚先关闭新受理/派发，排空或停止Runner、fence活跃租约，备份新事实。旧版本不认识新对象/状态时不能接管Agent Run；只读已提交结果需批准兼容reader，否则明确不可用，不退回线性执行。
6. 有新事实/checkpoint/未知用量时**禁止破坏性downgrade drop**；优先回滚应用并保留expand schema。清空受控测试环境才能验证破坏性down；正式删除须保留期/备份/审计批准且无未对账尝试。SQLite只验证有限约束，不能证明PG锁/partial index/Saver/权限一致。

## 10. 消费者签认与下一步

| 消费者 / Owner | 必须确认 | 状态 |
|---|---|---|
| M00 | 内部版本/03-A受理对接、发布边界与错误映射，ADR/迁移审批 | pending |
| M03 | Saver实际写入fencing能力、DDL/FK/索引、锁顺序、UoW/迁移/回滚 | pending |
| M01 / 安全 | active/owner/资源重检、State白名单、角色/加密/删除/访问边界 | pending |
| M05 | 固定版本、epoch/动作恢复、等待与取消、整份结果/事件发布 | pending |
| M06 | action/attempt/预扣/unknown/晚到对账、整数用量与追加审计 | pending |
| M11 | 真实PG多进程故障、权限/备份/版本/容量验证与证据分层 | pending |
| Owner / 业务运维安全 | 运行范围、保留/密钥/租约/备份策略来源、上线/回滚批准 | pending |

作者自审、schema和旧测试通过不能代签；04-A review非done，04-B~F和02~05父票保持blocked。当前独立前置提案全部已提交，下一步优先逐项签认、02-C目标平台锁验证及批准PG环境；不再把已写提案当新的ready业务任务。DR-010/011/TBD-P0/GATE全部不关闭。

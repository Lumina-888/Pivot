# 问枢 Pivot — SDD + TDD 开发总规格

| 项目 | 内容 |
|---|---|
| 文档 | `SPEC.md` |
| 版本 | SPEC-1.1 |
| 日期 | 2026-10-02 |
| 状态 | accepted：LangGraph 受控 ReAct 目标基线；实现迁移待完成，P0 参数待验证 |
| 专项规格 | [`spec/AGENT_SPEC.md`](spec/AGENT_SPEC.md) AGENT-SPEC-1.0 |
| 架构决策 | [`ADR-009`](progress/changes/20261002-M00-langgraph-react-baseline.md) |
| 历史来源 | [`技术方案GPT.md`](./技术方案GPT.md) GPT-1.0，仅历史参考 |
| 开发方法 | SDD（Specification-Driven Development）+ TDD（Test-Driven Development） |
| 适用阶段 | P0 预研、P1 MVP 开发与验收 |

> 本文件是当前规范源。SPEC-1.1 将旧固定线性 RAG 主图替换为 LangGraph + 受控 ReAct Agent；详细需求和实施门禁见专项规格。当前代码仍为旧线性实现，架构 accepted 不代表 LangGraph 已接入、答案漏洞已修复或 GATE 已验证。
>
> SPEC-1.0 和旧技术方案的主图、暂缓 LangGraph 及自由多 Agent 表述均不再作为当前开发目标；历史实现与测试证据保留。公开恢复接口、新错误映射和依赖版本需后续 Contract 冻结，未实现能力不得标为可用 API。
>
> 尚未通过真实文档、真实供应商和 ECS 压测验证的数值统一标记为 **`TBD-P0`**。实现人员不得在代码中私自把 `TBD-P0` 替换成未经记录的“默认值”；冻结后必须更新本文件、决策记录和测试夹具。

---

## 目录

- [0. 文档治理与开发规则](#0-文档治理与开发规则)
- [1. 范围、角色、术语与阶段边界](#1-范围角色术语与阶段边界)
- [2. 领域模型与业务不变量](#2-领域模型与业务不变量)
- [3. 状态机规格](#3-状态机规格)
- [4. 功能需求规格](#4-功能需求规格)
- [5. HTTP、SSE 与内部契约](#5-httpsse-与内部契约)
- [6. 文档接入、RAG 与答案可信度](#6-文档接入rag-与答案可信度)
- [7. 问答工作流与资源控制](#7-问答工作流与资源控制)
- [8. 安全、权限与数据治理](#8-安全权限与数据治理)
- [9. 运行、监控、备份与灾备](#9-运行监控备份与灾备)
- [10. TDD 测试规格](#10-tdd-测试规格)
- [11. 非功能需求](#11-非功能需求)
- [12. 验收标准、DoR/DoD 与阶段门禁](#12-验收标准dordod-与阶段门禁)
- [13. 追踪矩阵与交付节奏](#13-追踪矩阵与交付节奏)
- [附录 A：需求索引](#附录-a需求索引)
- [附录 B：API、错误码与事件索引](#附录-bapi错误码与事件索引)
- [附录 C：数据字典与状态枚举](#附录-c数据字典与状态枚举)
- [附录 D：测试命名、Fixture 与目录建议](#附录-d测试命名fixture-与目录建议)
- [附录 E：ADR 与开放决策登记](#附录-eadr-与开放决策登记)
- [附录 F：来源、历史冲突与原型差距](#附录-f来源历史冲突与原型差距)

---

## 0. 文档治理与开发规则

### 0.1 规格优先级

当多个文件出现不同表述时，按以下顺序解释：

1. 本文件中标记为“当前口径”“硬门槛”的内容；
2. 本文件引用的 [`AGENT_SPEC.md`](spec/AGENT_SPEC.md)，仅细化 Agent 需求，不独立覆盖总规格；
3. 已登记批准的 ADR；
4. `MODULE_SPEC.md` 的模块责任和 `spec/contracts/` 的已发布契约；
5. `PROGRESS.md`、`progress/` 的实现状态与开发计划（不是需求源）；
6. 技术方案 GPT、V2、A3 和 `风格样稿/`，仅作历史工程/产品/交互参考。

当前 Agent 路线仅为 LangGraph StateGraph + 原生工具调用型受控 ReAct。历史文件不再独立冻结编排架构；涉及旧内容的标注与取代记录见 ADR-009，不删除历史证据。A3 的“9 页”、旧方案的“证据面板常驻”、V2 的“内网 HTTP+IP”以及 S3 原型的 Mock 行为均不能覆盖本文件。

### 0.2 需求记录格式

每条需求必须具备以下字段：

| 字段 | 要求 |
|---|---|
| ID | 稳定、唯一，不因文字优化而改变 |
| 标题 | 一句话描述行为或约束 |
| 优先级 | P0/P1/P2/P3 |
| 阶段 | P0/P1/P2/P3 |
| Owner | 业务、产品、后端、前端、算法、运维或安全负责人 |
| 用户价值 | 为什么需要 |
| 前置条件 | Given 状态 |
| 主流程 | When/Then |
| 异常边界 | 失败、超时、空结果、权限等 |
| 契约 | API、事件、内部接口或数据结构 |
| 数据影响 | 写入、读取、派生和删除对象 |
| 测试 ID | 至少一个自动化测试或测试组 |
| 验收证据 | 报告、日志、截图或演练记录 |
| 依赖 | 外部服务、决策或其他需求 |
| 状态 | proposed/accepted/implemented/verified/deferred |

### 0.3 SDD 工作流

每个需求按以下顺序推进：

```text
需求提出
→ 需求评审
→ 规格接受（accepted）
→ 契约/数据模型冻结
→ 测试用例先行
→ 最小实现
→ 集成测试
→ E2E/非功能测试
→ 验收证据归档
→ 标记 verified
```

未达到 `accepted` 的需求不得进入实现；未关联测试的需求不得标记 `implemented`；未提供验收证据的需求不得标记 `verified`。

### 0.4 TDD 工作流

每个开发单元遵循：

1. **Red**：先写一个能明确表达失败原因的测试；
2. **Contract**：冻结输入、输出、错误和状态转移；
3. **Green**：用最小实现让测试通过；
4. **Refactor**：在测试保护下重构；
5. **Integration**：接入真实依赖或容器 Fixture；
6. **Regression**：运行受影响的 Golden Set、契约和回归测试。

禁止以“先写完整代码，之后补测试”作为默认流程。对外部 LLM、Embedding、Rerank 的测试必须使用可控 Fake/Stub，并另行安排供应商冒烟测试，不能把线上 API 波动当作单元测试结果。

### 0.5 DoR 与 DoD

**Definition of Ready（DoR）**：

- 需求 ID、优先级、Owner 已确认；
- 场景和异常边界已写出；
- API/事件/数据影响已确认；
- 依赖和开放决策已登记；
- 至少一个测试 ID 和验收证据类型已指定；
- 不存在未处理的阻断级歧义。

**Definition of Done（DoD）**：

- 单元、契约、集成或 E2E 测试通过；
- 关键安全和权限路径有负向测试；
- 日志、审计、错误处理和指标已接入；
- 文档、API Schema、迁移或配置已同步；
- 无新增未登记的 TBD；
- 验收证据已归档并关联需求 ID；
- 未破坏 Golden Set 和既有契约。

### 0.6 版本与变更

- 需求 ID、状态枚举、公开 API 字段和事件名一经发布不得随意复用；
- 破坏性 API 变更必须升级 `/api/v1` 或提供兼容窗口；
- 改变数据状态机、权限、引用语义、删除语义、模型或检索配置时，必须增加 ADR；
- P0 冻结的阈值、文件限制、保留期限和供应商政策必须有来源或实测报告；
- 任何历史文档同步修改都必须独立记录，不把本文件作为隐式修改依据。

---

## 1. 范围、角色、术语与阶段边界

### 1.1 MVP 产品范围

MVP 为纯 Web 系统，固定包含 **10 个产品页面**：

| 页面 | 路由 | 角色 |
|---|---|---|
| 登录 | `/login` | 全部 |
| 首页 | `/` | 登录用户 |
| 知识库列表 | `/library` | 登录用户 |
| 文档详情 | `/library/[id]` | 登录用户 |
| 全局搜索 | `/search?q=` | 登录用户 |
| 对话 | `/chat[/id]` | 登录用户 |
| 后台概览 | `/admin` | 管理员 |
| 文档管理 | `/admin/docs` | 管理员 |
| 用户管理 | `/admin/users` | 管理员 |
| 审计日志 | `/admin/audit` | 管理员 |

核心业务链路：

```text
上传 → 隔离 → 解析 → 分块 → Embedding → 索引发布
→ Agent 选择搜索/证据读取工具 → Observation → 有界再决策
→ 结构化证据答案 → 支持校验 → 持久化回答/拒答 → 导出/审计
```

### 1.2 角色

| 角色 | 权限边界 |
|---|---|
| 普通用户 | 浏览授权知识库、搜索、创建自己的会话、单文档提问、查看自己的答案/引用、导出授权内容 |
| 管理员 | 普通用户权限 + 用户管理、文档上传/更新/删除/重试、审计查询、基础运行指标 |
| 解析 Worker | 处理被授权的异步任务；不得自行扩大权限或访问无关文件 |
| 模型供应商 | 仅接收后端按策略发送的最小请求；不属于系统用户 |
| 审计查看者 | MVP 由管理员承担；只读查看审计，不得修改/删除事件 |

管理员是否可以查看其他用户完整会话需由 `DR-005` 明确。默认：管理员可查看安全审计和脱敏问答摘要，不默认查看完整敏感上下文。

### 1.3 非目标

MVP 不实现：

- 扫描 PDF OCR 和复杂表格还原；
- 跨文档对比、报告生成、HITL 大纲确认；
- Text2SQL 或写入型数据库操作；
- PDF 页内真实搜索和文本高亮；
- SSO、MFA、企业 IM；
- 手动多文档 `@` 组合；
- 独立“我的提问历史”归档页；
- 多机/K8s、高可用集群；
- 复杂文档级 ACL；
- 自由群聊式多 Agent、任意联网/Shell/代码执行；
- Agent 上传、删除、用户管理等写工具（既有显式管理 HTTP 不受影响）。

### 1.4 不可砍功能

即使排期紧张，以下功能不可从 MVP 主链路删除：

- 问答页及真实 LangGraph ReAct 工具决策闭环；
- 引用和证据抽屉；
- 无依据拒答；
- 单文档 scope 强制过滤；
- 服务端认证与资源授权；
- 基本审计；
- 备份与恢复演练。

### 1.5 原型边界

S3 完整原型用于确认信息架构、视觉和交互意图。原型中以下行为均不是生产能力：

- 任意非空账号即可登录；
- 静态数据和固定文档 ID；
- Toast 代替上传、导出、删除和跳转结果；
- 前端 chip 代替真实检索过滤；
- 模拟会话切换；
- 固定搜索结果和固定页面跳转。

生产实现必须以本文件的 API、数据、权限和测试契约为准。

---

## 2. 领域模型与业务不变量

### 2.1 存储职责

| 存储 | 事实/派生 | 允许内容 |
|---|---|---|
| PostgreSQL | 业务事实源 | 用户、权限、文档元数据、版本、Chunk 元数据、会话、Run、Claim、Citation、任务、审计、成本元数据 |
| MinIO | 对象存储 | 原始文件、解析中间物（按策略）、导出文件 |
| Qdrant | 可重建检索副本 | dense 向量、可选 sparse 向量、检索 payload |
| Redis | 队列/短期状态 | Celery 队列、短期缓存、限流计数；不保存唯一业务事实 |

核心不变量：

1. PostgreSQL 是业务事实源；
2. Qdrant 丢失后可以依据 PostgreSQL + MinIO 重建；
3. Redis 丢失不会造成业务事实不可恢复；
4. 审计不能只存在 Redis 或普通应用日志中；
5. Qdrant 中每个向量都能追溯到一个存在的 `version_id + chunk_id`。

### 2.2 核心对象

#### User / Role

```text
User(id, username, password_hash, role, status, token_version, created_at, updated_at)
Role ∈ {admin, user}
UserStatus ∈ {active, disabled}
```

不变量：停用用户不能登录、创建 Run、访问文档或导出；密码不得以明文、可逆形式或日志形式保存。

#### Document / DocumentVersion

```text
Document(document_id, title, space, tags, classification, created_by, deleted_at)
DocumentVersion(version_id, document_id, version_label, content_sha256,
  storage_key, status, current, effective_from, effective_to,
  external_llm_allowed, parser_version, chunking_version,
  embedding_model_version, index_generation)
```

不变量：同一逻辑文档最多一个有效的 `current=true` 版本；同一 `content_sha256` 的重复上传必须幂等或明确返回已存在版本；未完成发布的版本不得进入检索。

#### Chunk

```text
Chunk(chunk_id, version_id, text, text_hash, title_path, locator,
  raw_char_start, raw_char_end, published, created_at)
```

`locator` 按格式包含：PDF 页码/章节、DOCX 标题路径/段落、PPTX 幻灯片/标题、XLSX Sheet/单元格范围。

#### IndexGeneration

```text
IndexGeneration(generation_id, retrieval_config_version,
  embedding_model_version, dimension, status, created_at, published_at)
Status ∈ {building, validating, published, retired, failed}
```

只有 `published` 代次参与检索；Embedding 模型或维度变化必须创建新代次并全量重建。

#### Conversation / Message / Run

```text
Conversation(conversation_id, owner_id, title, scope_type,
  scope_document_id, created_at, updated_at)
Message(message_id, conversation_id, sender, content, status, run_id, created_at)
Run(run_id, conversation_id, message_id, question, scope_type,
  scope_document_id, idempotency_key, state, attempt, error_code,
  model_version, prompt_version, retrieval_config_version,
  index_generation, created_at, started_at, completed_at)
```

不变量：会话归属不可伪造；Run 不能扩大 Conversation 的 scope；有效幂等键不能产生多个业务 Run；Run 必须进入明确终态。

#### Evidence / Citation / Claim

```text
Citation(citation_id, run_id, claim_id, document_id, version_id,
  chunk_id, locator, snippet, confidence, retrieval_method)
Claim(claim_id, run_id, text, citation_ids, support, confidence)
Support ∈ {supported, uncertain, unsupported}
```

不变量：Citation 指向存在、已发布、可访问的 Chunk；`unsupported` Claim 不得进入 `answered`；不得虚构页码、章节或文档。

#### AgentEvent / AuditEvent / ProviderCall

```text
AgentEvent(event_id, run_id, stage, summary, seq, duration_ms, created_at)
AuditEvent(audit_event_id, actor, action, target, result, request_id, run_id, metadata, created_at)
ProviderCall(provider, model, operation, tokens, latency_ms, status,
  retry_count, estimated_cost, request_id, run_id)
```

AgentEvent 面向脱敏轻量轨迹，不保存完整思考链；AuditEvent 追加写；ProviderCall 记录调用尝试/用量，不保存不必要的完整敏感上下文。

#### AgentState / Checkpoint / ExecutionLease

AgentState 记录消息、合法工具观察、证据映射、执行游标、已消费预算和校验反馈。每 Run 使用服务端生成的独立 checkpoint thread；ExecutionLease 负责跨进程单执行者及 fencing。详细不变量见 AGENT_SPEC §5/§8。

Checkpoint 是敏感执行状态，不替代 PostgreSQL 的 Run/Message/Claim/Citation 事实；框架表和保留/加密策略经 DR-011 与迁移 Contract 冻结。Redis/进程内集合不得作为唯一执行或恢复事实。

#### ExportTask / CeleryTask / ParseError

```text
ExportTask(export_id, owner_id, source_type, source_id, format,
  status, storage_key, expires_at, created_at)
CeleryTask(task_id, entity_type, entity_id, attempt, state, retryable, created_at)
ParseError(error_id, version_id, code, message_summary, page, retryable, created_at)
```

### 2.3 聚合与删除

- `Document` 聚合拥有多个 `DocumentVersion`；
- `DocumentVersion` 聚合拥有多个 `Chunk` 和一个发布代次关联；
- `Conversation` 聚合拥有 `Message` 和 `Run`；
- `Run` 聚合拥有 `AgentEvent`、`Claim`、`Citation`、ProviderCall 元数据；
- `AuditEvent` 不属于可删除业务聚合，业务软删不得删除审计；
- 删除使用 tombstone：先从业务列表和检索中下线，再异步清理 Qdrant、缓存、导出物和原始对象；物理清理受保留策略约束。

---

## 3. 状态机规格

### 3.1 文档版本状态机

```text
uploaded → queued → parsing → chunking → embedding → indexed → ready
                                      ├→ parse_failed
                                      └→ embed_failed
ready → delete_pending → deleted / delete_failed
parse_failed / embed_failed → queued   [管理员重试]
delete_failed → delete_pending          [后台重试]
```

合法转移：

| 当前 | 事件 | 下一状态 | 必须满足 |
|---|---|---|---|
| uploaded | enqueue | queued | 任务幂等键建立 |
| queued | worker_started | parsing | 记录 task_id |
| parsing | parse_ok | chunking | 文本非空或有明确部分失败策略 |
| parsing | parse_error | parse_failed | 错误码稳定、不得发布 |
| chunking | chunk_ok | embedding | Chunk 数大于 0 |
| embedding | embedding_ok | indexed | 向量维度匹配 |
| embedding | embedding_error | embed_failed | 不得发布新代次 |
| indexed | validation_ok | ready | 抽样校验通过 |
| ready | delete_requested | delete_pending | 立即检索下线 |
| delete_pending | cleanup_ok | deleted | 审计保留 |
| delete_pending | cleanup_error | delete_failed | 可安全重试 |

禁止：已 `deleted` 版本重新变为 `ready`；未 `ready` 版本进入检索；重复消息产生重复 Chunk；新版本未验证就替换旧版本。

### 3.2 Run 状态机

```text
received → planning → retrieving → drafting → verifying → answered
              │           ↑  │                  │
              │           └──┼── 有界补证 ───────┘
              └→ waiting_for_user ← retrieving
                        ↓
                     resuming → retrieving
retrieving → retrying → retrieving     [仅基础设施临时故障]
任一非终态 → failed / cancelled
planning / retrieving / drafting / verifying → refused / uncertain
```

公开状态保持粗粒度，不新增 agent/tools 枚举。下表是合法转移的规范源，图仅为概览；具体事件映射由 M05 在 Contract 测试中实现。

| 当前状态 | 允许下一状态 | 约束 |
| --- | --- | --- |
| received | planning / failed / cancelled | 认领执行或失败/取消 |
| planning | retrieving / waiting_for_user / refused / uncertain / failed / cancelled | 输入/外发/预算门禁；澄清最多一次 |
| retrieving | drafting / retrying / waiting_for_user / refused / uncertain / failed / cancelled | 内部 Agent/工具循环不改变公开状态 |
| retrying | retrieving / refused / uncertain / failed / cancelled | 仅可重试基础设施故障；预算不重置 |
| waiting_for_user | resuming / failed / cancelled | 授权幂等恢复；等待期限仍 TBD-P0 |
| resuming | retrieving / refused / uncertain / failed / cancelled | 重检权限/资源/预算，不清零 |
| drafting | verifying / refused / uncertain / failed / cancelled | 严格结构化输出，禁止自由 Markdown fallback |
| verifying | answered / retrieving / refused / uncertain / failed / cancelled | 回检索仅限合法补证且有预算；回答须全量通过 |
| answered / uncertain / refused / failed / cancelled | 无 | 终态不可改写 |

规则：

- `idempotency_key` 重复提交返回已有 Run；
- `retrying` 只处理可重试错误；
- query rewrite 最多 2 次；
- 每次 Run 最多 1 轮用户澄清；
- 任一非终态可收到取消请求，但已完成终态不可改写；
- judge/Verifier 故障不得默认为 `answered`；只有合法补证路径可回到 Agent，权限/外发禁止不能靠循环绕过；
- 取消须传播到调用边界，晚到结果不得覆盖 cancelled；
- 当前实现的旧状态转移尚未迁移，旧测试成功不等于符合本节；
- 所有 Run 最终必须为 `answered`、`uncertain`、`refused`、`failed` 或 `cancelled`。

### 3.3 SSE 事件规则

事件类型：

```text
run_started, stage, token, citation, warning,
completed, uncertain, refused, failed, cancelled
```

每个事件必须带：

```text
run_id, message_id, seq, timestamp, stage, payload
```

`seq` 在一个 Run 内单调递增；终态事件最多一个；连接关闭不是业务终态；断线后使用 `Last-Event-ID` 补发，无法补发时读取 Run 状态接口。重连只能重放，不能重新执行 Agent。

校验前只发布白名单脱敏阶段摘要；最终 token/citation/completed 在答案校验、业务事实事务提交后发送。不得直接透传 LangGraph 原始事件、思考链、Prompt、工具原始参数或受保护 Observation。

### 3.4 用户状态机

```text
active ⇄ disabled
```

停用后立即阻止新登录和受保护资源访问；已有 Token 使用 `token_version` 或等效机制失效；启用/停用必须审计。

### 3.5 导出状态机

```text
requested → queued → generating → ready → expired
queued / generating → failed
```

过期文件不可下载；导出只读取已持久化答案，不重跑问答；导出内容和授权范围写入审计。

---

## 4. 功能需求规格

> 下列需求采用“需求说明 + Given/When/Then + 契约/数据 + 测试映射”的简化格式。完整实现时，每条需求应在追踪矩阵中补充 Owner、状态和验收证据路径。

### 4.1 认证与会话（`FR-AUTH-*`）

#### `FR-AUTH-001` 有效用户登录

- **优先级/阶段**：P0/P1；
- **场景**：Given `User.status=active` 且密码正确；When 提交登录；Then 建立会话并返回允许访问受保护 API 的凭证；
- **安全约束**：refresh token 仅通过 HttpOnly、Secure、SameSite Cookie；长期凭证不得放 localStorage；
- **测试**：`T-AUTH-001`、`T-CONTRACT-AUTH-001`；
- **验收**：登录 E2E、Cookie 属性检查、审计事件。

#### `FR-AUTH-002` 登录失败统一响应与限流

- **场景**：Given 用户不存在或密码错误；When 登录；Then 返回统一错误，不泄露“用户不存在/密码错误”的差异；记录失败登录并触发限流；
- **边界**：达到失败阈值后的窗口、解锁方式和数值为 `TBD-P0`；
- **测试**：`T-AUTH-002`、`T-SEC-LOGIN-RATE`；
- **验收**：安全测试报告和审计查询。

#### `FR-AUTH-003` 刷新、退出与停用失效

- **场景**：active 用户可刷新短时 access token；退出后 refresh token 不再可用；管理员停用用户后已有 Token 失效；
- **测试**：`T-AUTH-003`；
- **验收**：Token 生命周期集成测试。

#### `FR-AUTH-004` 密码生命周期

必须支持管理员创建用户、首次登录改密、重置密码、停用/启用；密码使用 Argon2id 或 bcrypt；初始密码不得通过普通日志或 URL 传输。

### 4.2 角色与资源授权（`FR-RBAC-*`）

#### `FR-RBAC-001` 管理 API 服务端 RBAC

- **Given**：普通用户凭有效 Token 请求 `/api/v1/admin/*`；
- **When**：调用接口；
- **Then**：返回 403 或统一无权限错误；前端是否隐藏入口不影响结果；
- **测试**：`T-RBAC-001`；
- **验收**：API 负向测试。

#### `FR-RBAC-002` 会话归属隔离

用户只能列出、读取、删除自己的会话和消息；管理员查看他人会话的能力需显式授权并审计，默认不返回完整敏感内容。

#### `FR-RBAC-003` 资源四重授权

检索、Citation、文档预览、下载、导出均必须重新执行服务端授权。猜测 `document_id`、`chunk_id`、`citation_id` 或 `export_id` 不得绕过授权。

#### `FR-RBAC-004` 共享库准入前提

若 MVP 继续使用共享知识库，则只有“全员可见且允许外发”的文档可进入 `ready`。业务不能保证时，必须在 P1 前启用空间/文档 ACL。

### 4.3 文档接入（`FR-DOC-*`）

#### `FR-DOC-001` 白名单格式

MVP 支持 `.pdf`、`.docx`、`.pptx`、`.xlsx`；默认拒绝 `.doc`、`.ppt`、`.xls`，除非先转换并通过独立验收。

#### `FR-DOC-002` MIME 与文件签名校验

文件扩展名、声明 MIME 和真实文件签名必须一致；伪装文件不得进入解析队列。测试：`T-DOC-SIGNATURE`。

#### `FR-DOC-003` 上传隔离与资源限制

上传先进入隔离区；解析 Worker 低权限运行、受限网络、隔离临时目录。以下限制必须由 P0 冻结：

```text
最大文件大小：TBD-P0
最大 PDF 页数：TBD-P0
最大 Sheet 数：TBD-P0
最大解压比例：TBD-P0
最大处理时长：TBD-P0
最大临时空间：TBD-P0
单次批量数量：TBD-P0
```

必须测试路径穿越、恶意 Office、压缩炸弹、超大文件和解析超时。

#### `FR-DOC-004` 解析错误可解释

至少支持错误码：`UNSUPPORTED_SCAN_PDF`、`ENCRYPTED_FILE`、`CORRUPTED_FILE`、`EMPTY_TEXT`、`UNSUPPORTED_EXTENSION`、`RESOURCE_LIMIT`、`PARTIAL_PAGE_FAILURE`。失败文档不得进入可检索状态。

#### `FR-DOC-005` 文档状态与任务幂等

重复上传请求、重复 Celery 消息、Worker 在提交前后崩溃均不得生成重复版本、Chunk 或索引；任务记录 attempt、错误码和 retryable。

#### `FR-DOC-006` 文档版本原子发布

新版本必须完成对象保存、解析、分块、Embedding、Qdrant 写入、抽样校验后才成为 `current=true`。新版本失败时旧版本保持可用。

#### `FR-DOC-007` 删除先下线后清理

删除请求先写 tombstone 并立即从列表和检索过滤中排除，再异步清理 Qdrant、缓存、导出物和原始对象；审计保留；清理失败可重试。

#### `FR-DOC-008` 孤儿扫描

定期检查 PostgreSQL、MinIO、Qdrant 间的孤儿版本、Chunk、向量和对象；扫描结果可审计，自动修复必须幂等。

### 4.4 搜索与检索（`FR-SEARCH-*`、`FR-RAG-*`）

#### `FR-SEARCH-001` 全局搜索

搜索支持关键词、摘要、类型、空间/标签筛选、分页和结果文档 ID；结果只能包含当前用户有权访问且 `ready/current` 的版本。

#### `FR-SEARCH-002` 搜索结果直接问 AI

用户从搜索结果进入对话时，应携带原问题；不得把搜索结果中的文档范围隐式扩大为全库或反之。

#### `FR-RAG-001` 默认混合检索

默认链路：

```text
dense top-50 + BM25 top-50
→ ready/current/期限/权限/scope 过滤
→ 去重
→ RRF
→ bge-reranker-v2-m3
→ top-5~8 evidence
```

RRF 参数、中文分词、数字/编号规则、rerank 超时和阈值为 `TBD-P0`。

#### `FR-RAG-002` 强制过滤

每个检索请求必须应用：`ready`、`current`、未过期、权限和结构化 scope。过滤必须发生在服务端检索层，不能只写在 Prompt 中。

#### `FR-RAG-003` 单文档 scope

- **Given**：`scope_type=document`、`scope_document_id=doc_A`；
- **When**：用户询问 doc_B 内容或 Prompt 要求扩大范围；
- **Then**：召回、证据、Citation、审计和最终答案只能绑定 doc_A；
- **测试**：`T-SCOPE-001`、`T-SEC-SCOPE-BYPASS`。

#### `FR-RAG-004` 单路失败降级

Dense 失败可降级 BM25，BM25 失败可降级 Dense；两路均失败或过滤后无证据时不得生成无引用事实答案；错误必须进入 ProviderCall/Run 记录。

#### `FR-RAG-005` 版本冲突透明展示

多个有效版本冲突时展示文档、版本、生效时间和各自证据；不得由模型静默选择。优先级字段和生效区间必须参与检索或结果解释。

#### `FR-RAG-006` 索引代次可追溯

检索结果关联 `index_generation`、`embedding_model_version`、`retrieval_config_version`；模型或维度变化创建新代次并全量重建。

### 4.5 问答与 Agent（`FR-QA-*`）

#### `FR-QA-001` LangGraph 受控 ReAct 主图

目标为真实 StateGraph 条件循环：Agent 通过原生工具调用选择行动，接收 Observation 后再次决策，直到澄清、提出结构化答案或安全结束。图见 §7.1，细则见 AGENT_SPEC。

模型不能决定权限、扩大 scope、改变工具白名单或跳过答案校验。检索仍由既有混合检索实现；只将线性调用包装成图不满足 FR-AGENT-001。当前纯 Python 线性实现是迁移基线，不是新需求已实现。

#### `FR-QA-002` 结构化 Claim/Citation

模型输出严格结构化 Claims 与本 Run evidence_ids；服务端生成真实 Citation 并校验存在性、版本、候选归属、权限及文本支持关系。最终 Markdown 只能从通过校验的事实渲染，Claims/Citation/最终 Message/终态幂等事务提交后才公开。

禁止“模型自由 Markdown + 从证据另生成的 Claims”fallback；候选合法不代表事实被支持。首版任一事实 Claim 不通过则整份候选不发布，有限补证后全量通过才可 answered。

#### `FR-QA-003` 无依据拒答

单次合法空检索可作为 Observation，在预算内触发新查询；预算耗尽或无合法补证路径后仍无命中、低相关性、权限过滤后无证据或冲突未解决时，Run 进入 `uncertain` 或 `refused`。外发禁止不得通过换工具/供应商绕过；不得使用常识补全企业事实。

#### `FR-QA-004` Citation Verifier 安全降级

Verifier/judge 超时、不可用或返回非法结构时，不得默认为通过。支持性不足可在预算内合法补证，否则存疑或拒答；首版不局部忽略非法 Claim 后保留整段答案。局部删句发布策略须后续独立 ADR。

#### `FR-QA-005` 轻量轨迹

普通用户只能看到路由、检索、重排、合成、校验等阶段和结果摘要；不得暴露完整思考链、系统 Prompt、敏感 Chunk、内部工具参数或密钥。

#### `FR-QA-006` 澄清与上下文隔离

每个 Run 最多 1 轮澄清；通过 LangGraph interrupt/checkpoint 保留上下文，经会话 owner 授权恢复同一 Run，累计预算不重置。Worker 不保存跨任务记忆；不同用户会话绝不共享上下文。公开恢复接口在后续 Contract 冻结，当前 v0.1 尚不提供该接口。

#### `FR-AGENT-001~010` 专项需求

Agent 循环、只读工具、可信上下文/外发、预算、答案发布、checkpoint/租约、澄清恢复、安全轨迹/取消、模型能力和评测的 Owner、场景、数据、测试与验收见 [`AGENT_SPEC §2`](spec/AGENT_SPEC.md#2-需求登记与追踪)。状态为 accepted，未实现；既有 FR-QA/FR-STREAM ID 保留。

### 4.6 Run/SSE（`FR-STREAM-*`）

#### `FR-STREAM-001` Run 幂等创建

相同用户、会话和有效 `idempotency_key` 的重复请求返回同一 Run；重复 HTTP/SSE 请求不得重复启动有效执行或创建 Message。跨进程认领和取消/终态竞争须有数据库约束。

Checkpoint 不保证供应商调用/计费 exactly-once；崩溃重放需调用尝试登记、幂等键（供应商支持时）及用量对账，残余风险须在验收中记录，不能宣称框架自动消除重复计费。

#### `FR-STREAM-002` SSE 有序事件

事件包含 `run_id/message_id/seq/stage/payload`；seq 单调递增；终态唯一；前端不得因重复事件渲染重复答案。

#### `FR-STREAM-003` 断线重连

支持 `Last-Event-ID` 补发；补发不可用时客户端查询 Run 最终状态；SSE 不是唯一事实来源。

#### `FR-STREAM-004` 取消

Run 所有者或有权限管理员可取消未完成 Run；取消幂等；已完成 Run 不得改写；取消须尽可能传递到 LLM、检索和 Worker。

#### `FR-STREAM-005` 超时和重试预算

仅超时、429、临时 5xx、临时网络错误可走基础设施重试；权限、格式、已确定无合法补证路径或禁止外发不可重试。单次合法空观察可在预算内触发新的查询行动，不等于重试权限/格式错误。query rewrite 最多 2 次，具体调用数/总超时/单步超时/token/费用上限为 `TBD-P0`；恢复/备用模型不重置预算。

### 4.7 导出（`FR-EXPORT-*`）

#### `FR-EXPORT-001` 授权导出

导出校验用户、会话/文档权限、来源对象归属、格式和任务状态；下载使用短时授权，不暴露 MinIO 内部地址。

#### `FR-EXPORT-002` 导出内容边界

仅导出已持久化最终答案、Claims、Citation 和允许展示的定位/证据；不得包含 Prompt、完整思考链、隐藏工具参数或未展示敏感上下文。

#### `FR-EXPORT-003` 导出过期与审计

导出文件自动过期，过期后不可下载；创建、下载、失败和过期均写入审计。文件名必须清洗。

### 4.8 审计（`FR-AUDIT-*`）

#### `FR-AUDIT-001` 关键事件覆盖

至少审计：登录、失败登录、退出、角色变更、用户停用、上传、更新、删除、重试、问答、导出、管理员调试访问、权限变化、备份恢复和配置变化。

#### `FR-AUDIT-002` 追加写和脱敏

普通应用账号不得修改/删除审计；管理员页面只读；问题、引用、文档和 Prompt 内容按数据分级脱敏；特权访问本身也须审计。

#### `FR-AUDIT-003` 问答可复盘

问答审计至少可追踪 `request_id/run_id`、用户、状态、命中文档、Citation、模型、Prompt/角色卡版本、检索参数、索引代次、重试和耗时。

---

## 5. HTTP、SSE 与内部契约

### 5.1 通用 HTTP 规则

- Base URL：`/api/v1`；
- ID：不透明字符串，禁止依赖自增 ID 暴露业务顺序；
- 时间：ISO 8601 UTC；
- 分页：`page`/`page_size` 或 cursor 方案必须统一，最终为 `TBD-P0`；
- 错误包：

```json
{
  "code": "RESOURCE_FORBIDDEN",
  "message": "无权访问该资源",
  "request_id": "req_001",
  "details": {},
  "retryable": false
}
```

- 所有错误都带 `request_id`；不返回 Secret、堆栈或敏感上下文；
- 写操作按需支持 `Idempotency-Key`；
- API Schema 后续应从本节生成 `contracts/openapi.yaml`，当前本文件是规范源。

### 5.2 认证接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/login` | 登录 |
| POST | `/auth/refresh` | 刷新 access token |
| POST | `/auth/logout` | 退出并撤销刷新凭证 |
| POST | `/auth/change-password` | 修改密码 |

### 5.3 文档与搜索接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/documents` | 列表、筛选、分页 |
| POST | `/documents` | 管理员上传，建议 multipart + 幂等键 |
| GET | `/documents/{id}` | 详情 |
| GET | `/documents/{id}/versions` | 版本列表 |
| POST | `/documents/{id}/retry` | 重试失败任务 |
| POST | `/documents/{id}/delete` | 软删并触发清理 |
| GET | `/documents/{id}/preview` | 授权预览 |
| GET | `/documents/{id}/download` | 授权下载 |
| GET | `/search` | 文档搜索和筛选 |

上传请求必须包含或产生：`title`、`space`、`tags`、`classification`、`external_llm_allowed`、文件对象、`content_sha256`（可由服务端计算）。

### 5.4 会话与 Run 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/conversations` | 当前用户会话列表/创建 |
| GET | `/conversations/{id}` | 会话详情 |
| DELETE | `/conversations/{id}` | 删除或隐藏当前用户会话 |
| GET | `/conversations/{id}/messages` | 当前用户消息 |
| POST | `/runs` | 创建问答运行 |
| GET | `/runs/{id}` | 状态和最终结果 |
| GET | `/runs/{id}/events` | SSE 事件 |
| POST | `/runs/{id}/cancel` | 取消运行 |

`POST /runs` 请求：

```json
{
  "conversation_id": "conv_001",
  "question": "请说明迟到处理规则",
  "scope_type": "document",
  "scope_document_id": "doc_001",
  "idempotency_key": "idem_001"
}
```

返回至少：`run_id`、`message_id`、`initial_state`、`request_id`。

ReAct 澄清恢复的公开 endpoint、字段、幂等与错误映射在 ND-AGENT-03 的 M00 Contract 冻结；本次不新增可调用路由。当前机器可读 contract-v0.1 是已发布兼容信封，不代表 FR-AGENT 已实现。未冻结恢复接口前不得私自实现或生成客户端。

### 5.5 导出和后台接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/exports` | 创建 Markdown/Word 导出任务 |
| GET | `/exports/{id}` | 查询状态和短时下载地址 |
| GET | `/admin/metrics` | 基础指标 |
| GET | `/admin/tasks` | 解析任务和队列 |
| GET/POST/PATCH | `/admin/users[/{id}]` | 用户管理 |
| GET | `/admin/audit-events` | 审计查询 |

### 5.6 SSE 事件契约

```json
{
  "run_id": "run_001",
  "message_id": "msg_001",
  "seq": 17,
  "timestamp": "2026-09-06T08:00:00Z",
  "stage": "verifying",
  "payload": {}
}
```

事件名：`run_started`、`stage`、`token`、`citation`、`warning`、`completed`、`uncertain`、`refused`、`failed`、`cancelled`。每个 Run 最多一个终态事件。

### 5.7 内部 Worker 契约

```json
{
  "status": "ok",
  "content": {},
  "citations": [],
  "confidence": null,
  "error_code": null,
  "trace": {
    "stage": "retrieve",
    "duration_ms": 0
  }
}
```

`status ∈ {ok, insufficient, failed}`。Worker 不得改变权限范围、调用未白名单工具或保存跨任务记忆。

---

## 6. 文档接入、RAG 与答案可信度

### 6.1 解析规格

解析器接口必须可插拔：

- MVP：PyMuPDF/pdfplumber、python-docx、python-pptx、openpyxl；
- V2：MinerU 云 API，用于 OCR 和复杂表格；
- 扫描 PDF、加密文件、损坏文件、空文本和资源超限不得静默入库。

文件限制为 `TBD-P0`：大小、页数、Sheet 数、解压比例、文本量、处理时长、临时空间和批量数量。

### 6.2 分块规格

初始参数：普通文本 400~800 token，重叠 50~100 token；P0 根据 Golden Set 冻结。每个 Chunk 必须保存：标题路径、文档/版本、格式定位、字符偏移、文本 hash、chunk_id 和 index_generation。

表格使用“表头 + 行组”策略，超长表格重复表头；列表尽量保持条目完整；不跨版本混块。

### 6.3 检索规格

默认链路：

```text
dense top-50 + BM25 top-50
→ ready/current/未过期/权限/scope 过滤
→ 去重
→ RRF
→ bge-reranker-v2-m3
→ top-5~8 evidence
```

必须冻结：Dense 距离函数、BM25 中文分词、数字/编号保留、RRF 参数、rerank 超时和阈值。Qdrant sparse encoder 只能在 P0 对比通过后替换 BM25，并触发新索引代次。

### 6.4 Citation 与 Claim

```json
{
  "claim_id": "claim_001",
  "text": "具体论断",
  "citation_ids": ["cit_001"],
  "support": "supported",
  "confidence": null
}
```

Citation 必须指向当前用户可访问的 Chunk；候选集合外或悬空 Citation 直接判错；Claim 与 Citation 绑定及原文支持关系必须验证。只渲染通过的结构化事实，不接受另一份自由 Markdown；定位不支持时展示证据原文和限制提示。

### 6.5 拒答和 Verifier

以下任一情况不得输出无引用事实答案：

- 无命中；
- 相关性低于 P0 阈值；
- 权限过滤后无证据；
- 版本冲突未显式处理；
- 数据外发不允许；
- Verifier/judge 失败且无法安全降级。

处理结果可为 `uncertain`、`refused` 或 `failed`。Judge 仅为辅助；人工标注优先于 Judge。

---

## 7. 问答工作流与资源控制

本节为 LangGraph ReAct 的全局约束，内部图、工具、State、checkpoint 和验收见 [`AGENT_SPEC.md`](spec/AGENT_SPEC.md)。ADR-009 已取代旧固定线性主图；不再把 LangGraph 当可无限期推迟的可选目标。

### 7.1 MVP 主图

```text
START → input_guard → load_context → agent
agent → tool_guard → search_knowledge/read_evidence → observation_guard → agent
agent → clarify/interrupt → authorized_resume → agent
agent → build_evidence → structured_finalize → verify
verify → persist_result → END                         [通过]
verify → repair_feedback → agent                     [合法补证且有预算]
verify → refuse_or_uncertain → persist_result → END   [无合法补证路径]
```

模型通过原生工具调用与 Observation 选择行动，服务端决定工具许可、身份/scope、外发、预算和发布。ReAct 不要求公开完整 Thought；不使用自由文本 Thought/Action 正则模拟工具协议。

### 7.2 节点职责

| 节点 | 可以做 | 禁止做 |
|---|---|---|
| Agent | 选择只读工具/查询、根据观察继续或提出结束/澄清 | 决定权限、直接发布未验证答案 |
| ToolGuard / Tools | 服务端授权、调用现有混合检索或读取合法证据、返回限长观察 | 任意联网/执行代码、写操作、扩大 scope |
| Finalizer | 仅从合法证据生成结构化事实与 evidence_ids | 输出另一份未经验证的正式 Markdown、虚构定位 |
| Verifier / Publisher | 候选/绑定/文本支持检查、只渲染通过事实、事务提交后发布 | 故障放行、终态覆盖、校验前发布事实 |
| AgentRunner | 认领、预算、取消、checkpoint 恢复、公开事件投影 | 把 SSE 重连视为重新执行 |

### 7.3 预算控制

- query rewrite 最多 2 次；每 Run 最多 1 轮澄清；
- 最大工具/模型调用数、观察长度、单步/总超时、token/费用、并发与 recursion_limit：`TBD-P0`，DR-010；
- recursion_limit 不替代业务预算；恢复/重试/备用供应商共享累计预算；
- 仅超时、429、临时 5xx 和临时网络错误可走基础设施重试；合法空观察后的新查询不是权限/格式错误重试；
- 每次行动、重试、ProviderCall、图/Prompt/工具版本及索引代次必须追踪；
- 一 Run 一服务端 thread_id，checkpoint 不替代业务事实；保留/加密/一致性策略见 DR-011；
- 依赖预算、恢复接口或 checkpoint 策略的切片未满足 DoR 时先冻结 Contract，不私设默认。

### 7.4 迁移与验收

ND-AGENT-01 答案安全回归优先，然后模型/工具 Contract 与真实 LangGraph 闭环、Run/SSE/澄清集成、持久恢复和 live 评测。旧线性代码、历史绿灯及依赖安装不能验收 FR-AGENT；当前实现差距和默认下一刀见 PROGRESS.md。

---

## 8. 安全、权限与数据治理规格

### 8.1 认证与网络

- 默认 HTTPS；必要时通过 VPN/反向代理访问；
- 数据库、Qdrant、Redis、MinIO 不暴露公网；
- Argon2id 或 bcrypt；
- 短时 access token + HttpOnly/Secure/SameSite refresh cookie；
- 登录失败限流、密码重置、首次改密、停用立即失效；
- CORS 白名单、CSRF、防 XSS、安全响应头；
- 前端 middleware 不能代替后端授权。

### 8.2 文件与 Prompt 安全

- MIME、扩展名、文件签名双重校验；
- 上传隔离区、病毒/恶意文件扫描能力或等效控制；
- 解析 Worker 低权限、受限网络、资源限额；
- 文件名规范化，防路径穿越和压缩炸弹；
- 文档内容视为不可信数据而非系统指令；
- 工具白名单、参数校验、禁止模型自行扩大 scope；
- Markdown/HTML 采用安全白名单清洗。

### 8.3 外部模型数据门禁

文档版本必须包含 `classification` 与 `external_llm_allowed`。上传时、工具执行/恢复时及每次模型调用前检查；Planner、Finalizer、Verifier、备用供应商和历史/摘要/Observation 均受同一外发门禁。禁止将受限正文的衍生摘要通过历史消息外发。未完成供应商区域、留存、训练使用、删除政策和 IT/法务/安全审批前，只允许低敏或脱敏文档。

### 8.4 审计

安全审计、问答审计和调试 Trace 分层；至少覆盖登录、失败登录、角色变更、用户停用、上传、更新、删除、重试、问答、导出、权限变化、管理员调试、备份恢复和配置变化。

审计追加写、普通应用账号不可修改/删除、敏感内容脱敏、特权访问留痕、审计独立备份。

---

## 9. 运行、监控、备份与灾备规格

### 9.1 Compose 运行约束

- ECS 4C8G，Docker Compose，固定镜像 tag 或 digest；
- 服务配置 healthcheck、启动依赖和资源 limits/reservations；
- Celery 解析队列与在线任务队列隔离，并明确 worker concurrency；
- 日志轮转、临时目录配额、磁盘水位告警；
- 发布流程：备份 → 固定版本 → 迁移 → 启动 → health/ready → 冒烟 → 观察 → 回滚。

### 9.2 可观测性

必须提供：

```text
/healthz
/readyz
```

监控 PostgreSQL、Qdrant、Redis、MinIO 可用性、CPU/内存/磁盘、队列、解析/问答失败、SSE 中断、供应商延迟和错误、费用、备份和证书。

### 9.3 备份与恢复

初始目标：

```text
RPO ≤ 24 小时
RTO ≤ 4 小时
```

最终值必须经 P0 新 ECS 演练确认。备份主位置为加密 OSS，本地仅短期缓存；备份账号独立、最小权限、禁止公网访问。至少备份 PostgreSQL、MinIO 原文/导出物、Qdrant snapshot 或重建配置、审计和恢复所需 Compose/迁移文件。Redis 若只保存可重建状态，必须明确；若承载不可重建任务状态，则须持久化。

恢复后校验用户、文档、版本、Chunk、向量、Citation、审计和抽样问答；备份成功/失败均告警。

---

## 10. TDD 测试规格

### 10.1 测试层级

| 层级 | 目标 | 典型范围 |
|---|---|---|
| 单元 | 快速验证纯逻辑 | 状态机、权限、scope、RRF、分块、定位、引用、重试、幂等、成本 |
| 契约 | 防止接口漂移 | OpenAPI、错误包、SSE schema、事件序号/终态、Worker schema |
| 集成 | 验证组件协作 | PG/MinIO/Qdrant/Redis/Celery、上传、索引、删除、供应商 Stub |
| E2E | 验证用户链路 | 10 页、登录、上传、搜索、问答、引用、拒答、导出、审计 |
| 安全 | 验证边界 | 越权、Token、XSS/CSRF、恶意文件、Prompt Injection、日志/Secret |
| 性能/可靠性 | 验证容量和故障 | 5 并发、100k Chunk、服务/供应商故障、SSE、磁盘满、回滚 |
| Golden Set | 验证质量回归 | 人工标注 100~150 条，LLM judge 仅辅助 |

### 10.2 单元测试清单

- 文档、Run、导出状态机合法/非法迁移；
- 用户和资源权限判断；
- scope 构造与不可扩大；
- BM25 关键词处理、RRF 计算、去重；
- 分块和四类 locator；
- Claim-Citation 引用合法性；
- 错误码和 retryable 判定；
- 幂等键、重试预算、指数退避；
- 文件名清洗、MIME/签名校验；
- 成本估算和额度判断。

### 10.3 契约测试清单

- HTTP 请求/响应 Schema；
- 统一错误包字段和状态码；
- 分页、时间和 ID 格式；
- SSE 事件 schema、seq 递增、唯一终态、Last-Event-ID；
- `scope_type`/`scope_document_id` 前后端一致；
- 导出短时下载响应；
- API 认证和版本兼容。

### 10.4 集成测试清单

- 四类白名单文档上传到 `ready`；
- 异常文件进入明确失败状态；
- 重复消费和 Worker 重启幂等；
- 新版本构建、验证、原子发布；
- 删除下线和异步清理；
- Dense + BM25 + RRF + Rerank；
- Run 落库、SSE、断线恢复和取消；
- 外部供应商 429/5xx/超时；
- 导出和审计；
- 备份/恢复 Fixture。

### 10.5 E2E 场景

1. 用户登录并访问首页；
2. 浏览知识库并筛选；
3. 管理员上传合法 PDF；
4. 文档进入队列并最终 `ready`；
5. 全局搜索并打开正确文档；
6. 创建会话并发送问题；
7. SSE 流式收到阶段、Token、Citation 和终态；
8. 点击引用打开证据抽屉；
9. 无答案问题得到拒答；
10. 从文档详情进入单文档问答且不串库；
11. 导出已完成答案；
12. 管理员查询审计；
13. 删除文档后立即无法检索；
14. 普通用户访问后台和他人会话均被拒绝。

### 10.6 安全测试

覆盖 JWT 伪造/过期、停用 Token、RBAC 越权、预览/下载/Citation/导出授权、XSS/Markdown、CSRF/CORS、路径穿越、恶意上传、压缩炸弹、Prompt Injection、日志敏感信息、Secret 泄露、MinIO 直接访问和 ID 猜测。

### 10.7 性能与可靠性测试

覆盖 5 并发问答、100,000 Chunk 检索、1/2/5 解析任务、上传/问答/导出并行、供应商 429/5xx/超时、Dense/BM25/Rerank 失败、Redis/PG/Qdrant 重启、Worker 退出、SSE 断线、磁盘满、发布失败和回滚。

### 10.8 Golden Set 回归

Agent 还需覆盖 Observation 改变工具选择、多轮改写/读证据、工具协议非法、预算、注入、取消、跨用户/跨 Run 和 checkpoint 恢复。Fake/Stub 替换模型/基础设施，不替换真实 StateGraph。数据/测试追踪见 AGENT_SPEC §2/§11。

样本分层：事实、编号/金额/日期/参数、多段组合、无答案、近似干扰、版本冲突、单文档 scope、解析失败、Prompt Injection 和越权。每条样本保存问题、期望证据、允许答案、是否应拒答、人工标注、数据集版本和回归结果。

---

## 11. 非功能需求（NFR）

### 11.1 容量（`NFR-CAP-*`）

| ID | 要求 | 当前状态 |
|---|---|---|
| `NFR-CAP-001` | 首批用户 5~10 人 | 已定 |
| `NFR-CAP-002` | 在线问答不超过 5 并发 | 已定，需压测 |
| `NFR-CAP-003` | 起步万级 Chunk | 已定 |
| `NFR-CAP-004` | 目标 100,000 Chunk | 需 P0 验证 |
| `NFR-CAP-005` | 解析并发 1/2/5 任务测试 | P0 |
| `NFR-CAP-006` | ECS 4C8G + Compose + 免 GPU | 已定，需容量验证 |

### 11.2 性能（`NFR-PERF-*`）

- `NFR-PERF-001` 已校验正式答案首 Token P50/P95 ≤ `TBD-P0`，与首次阶段进度耗时分开记录；
- `NFR-PERF-002` 完整答案 P50/P95 ≤ `TBD-P0`；
- `NFR-PERF-003` 检索 P95 ≤ `TBD-P0`；
- `NFR-PERF-004` 解析耗时和吞吐 ≤ `TBD-P0`；
- `NFR-PERF-005` 导出 P95 ≤ `TBD-P0`；
- `NFR-PERF-006` SSE 断线恢复时延 ≤ `TBD-P0`。

### 11.3 质量（`NFR-QUAL-*`）

- `NFR-QUAL-001` Recall@5 ≥ `TBD-P0`；
- `NFR-QUAL-002` Recall@10 ≥ `TBD-P0`；
- `NFR-QUAL-003` Citation 支持率 ≥ `TBD-P0`；
- `NFR-QUAL-004` Citation 精确率 ≥ `TBD-P0`；
- `NFR-QUAL-005` Citation 完整率 ≥ `TBD-P0`；
- `NFR-QUAL-006` 答案事实正确率 ≥ `TBD-P0`；
- `NFR-QUAL-007` 答案有用性 ≥ `TBD-P0`；
- `NFR-QUAL-008/009` 拒答 precision/recall ≥ `TBD-P0`；
- `NFR-QUAL-010` 端到端成功率 ≥ `TBD-P0`；
- `NFR-QUAL-011` 解析成功率 ≥ `TBD-P0`；
- `NFR-QUAL-012` 索引发布成功率 ≥ `TBD-P0`。

判定以人工标注为主，LLM judge 为辅助；阈值冻结后必须记录数据集版本和回归容差。

### 11.4 安全（`NFR-SEC-*`）

- `NFR-SEC-001` 默认 HTTPS/VPN/反向代理；
- `NFR-SEC-002` 后端强制认证；
- `NFR-SEC-003` 后端强制 RBAC；
- `NFR-SEC-004` Argon2id/bcrypt；
- `NFR-SEC-005` HttpOnly/Secure/SameSite；
- `NFR-SEC-006` CORS 白名单；
- `NFR-SEC-007` CSRF 防护；
- `NFR-SEC-008` Markdown/HTML 白名单；
- `NFR-SEC-009` 文件签名校验；
- `NFR-SEC-010` 上传隔离；
- `NFR-SEC-011` 压缩炸弹/资源耗尽防护；
- `NFR-SEC-012` Prompt Injection 测试；
- `NFR-SEC-013` 日志脱敏；
- `NFR-SEC-014` Secret 不进代码、镜像、前端和日志；
- `NFR-SEC-015` 文件短时授权；
- `NFR-SEC-016` 内部存储不暴露公网。

### 11.5 可观测性（`NFR-OBS-*`）

- `NFR-OBS-001` `/healthz`；
- `NFR-OBS-002` `/readyz`；
- `NFR-OBS-003` 结构化日志；
- `NFR-OBS-004` request/run/provider 关联；
- `NFR-OBS-005` 队列和任务指标；
- `NFR-OBS-006` 外部供应商指标；
- `NFR-OBS-007` 备份告警；
- `NFR-OBS-008` 证书告警。

### 11.6 灾备和体验（`NFR-DR-*`、`NFR-UX-*`）

- `NFR-DR-001` 初始 RPO ≤24 小时，P0 实测冻结；
- `NFR-DR-002` 初始 RTO ≤4 小时，P0 实测冻结；
- `NFR-DR-003` 加密 OSS 备份和独立权限；
- `NFR-DR-004` 新 ECS 恢复并完成冒烟；
- `NFR-UX-001` 主要流程键盘可操作；
- `NFR-UX-002` `:focus-visible` 和弹层焦点管理；
- `NFR-UX-003` 流式/Toast 状态具备 `aria-live`；
- `NFR-UX-004` 支持 `prefers-reduced-motion`；
- `NFR-UX-005` 明确 Chrome/Edge 版本范围。

---

## 12. 验收标准、DoR/DoD 与阶段门禁

### 12.1 需求验收要求

每条需求必须能沿以下链路追溯：

```text
需求 ID → 场景 ID → 契约/数据 → 测试 ID → 验收证据 → verified
```

验收证据可为 CI 报告、契约测试、Golden Set 报告、压测报告、安全清单、恢复演练日志、迁移/回滚记录或生产前截图/录屏。截图不能替代自动化测试。

### 12.2 P0 八项硬门槛

| ID | 门槛 | 未通过后果 |
|---|---|---|
| `GATE-P0-001` | 数据合规和外发审批 | 禁止真实企业文档 |
| `GATE-P0-002` | RAG（dense+BM25/备选 sparse）闭环 | 不进入 P1 |
| `GATE-P0-003` | 状态一致性、幂等、删除和索引原子发布 | 禁止生产上传 |
| `GATE-P0-004` | 引用、拒答、Verifier 和 scope 可信 | 只能内部实验 |
| `GATE-P0-005` | 认证、RBAC、上传隔离和日志安全 | 禁止上线 |
| `GATE-P0-006` | 加密备份、新 ECS 恢复、RPO/RTO | 不得正式试用 |
| `GATE-P0-007` | 5 并发、100k Chunk 和资源峰值 | 限制容量或延期 |
| `GATE-P0-008` | 固定版本、发布、健康检查和回滚 | 禁止自动升级 |

### 12.3 P1 进入与退出

**进入 P1**：所有 P0 阻断门槛关闭；数据准入规则生效；API/数据状态契约已冻结；第一批 TDD 测试和 Fixture 已建立。

**退出 P1**：10 页真实系统可用；功能、安全、性能、可靠性、灾备矩阵通过；低敏文档内测可回放；无未登记阻断级缺陷。

### 12.4 验收矩阵

| 功能域 | 必测场景 | 结果字段 |
|---|---|---|
| 认证 | 成功、失败、刷新、退出、停用 | 测试 ID、日志、结果 |
| RBAC | 普通用户后台、会话、资源越权 | API 响应、报告 |
| 文档 | 上传、签名、解析、重试、版本、删除 | 状态、任务、计数 |
| RAG | 混合检索、过滤、scope、降级、冲突 | 检索结果、Golden Set |
| 问答/Agent | 原生工具循环、合法证据、引用支持、拒答、预算、澄清/恢复、取消 | Run、Claim、Citation、Checkpoint、ProviderCall |
| SSE | 有序、断线、重连、取消、终态 | 事件记录 |
| 导出 | 授权、内容边界、过期、审计 | 文件和审计 |
| 运维 | 健康、重启、备份、恢复、回滚 | Runbook 记录 |

---

## 13. 追踪矩阵与交付节奏

### 13.1 追踪矩阵模板

| 需求 ID | 优先级 | 阶段 | Owner | 设计/章节 | 契约/对象 | 测试 ID | 验收证据 | 状态 | 阻断性 |
|---|---|---|---|---|---|---|---|---|---|
| `FR-RAG-003` | P0 | P0/P1 | 算法/后端 | §6 | scope、Citation | `T-SCOPE-001` | scope 越权报告 | proposed | 是 |
| `FR-DOC-006` | P0 | P0/P1 | 后端 | §3/§6 | DocumentVersion | `T-DOC-VERSION` | 原子发布报告 | proposed | 是 |
| `FR-STREAM-003` | P1 | P0/P1 | 后端/前端 | §3/§5 | SSE event | `T-SSE-RECONNECT` | 契约+E2E | proposed | 是 |
| `NFR-DR-002` | P0 | P0 | 运维 | §9/§11 | backup/runbook | `T-DR-RESTORE` | 恢复演练 | proposed | 是 |

### 13.2 第一批 TDD 顺序

1. **安全边界和状态一致性**：`FR-RBAC-001/003`、`FR-DOC-002/005/006/007`、`FR-RAG-002/003`、Run 幂等；
2. **问答可信度**：Claim/Citation、拒答、Verifier 失败、版本冲突；
3. **契约与体验**：REST、SSE、重连、取消、导出；
4. **性能和灾备**：5 并发、100k Chunk、供应商故障、恢复和回滚。

### 13.3 阶段交付物

| 阶段 | 交付物 | 退出条件 |
|---|---|---|
| P0 | 最小链路、Golden Set、模型盲评、合规、状态/API 草案、压测、恢复和安全报告 | P0 八项门槛结论 |
| P1 | 10 页 Next.js、FastAPI、文档管理、问答、引用、拒答、导出、RBAC、审计、Compose | 功能/非功能矩阵通过 |
| P2 | OCR/复杂表格、对比、报告 HITL、Text2SQL 只读、页内高亮、SSO | 各能力独立契约和评测通过 |
| P3 | 常态回归、集中观测、成本优化、多机/K8s、ACL/密级和合规加固 | 企业化门槛通过 |

---

## 附录 A：需求索引

### 认证与授权

`FR-AUTH-001~004`、`FR-RBAC-001~004`

### 文档

`FR-DOC-001~008`

### 搜索与 RAG

`FR-SEARCH-001~002`、`FR-RAG-001~006`

### 问答与流式

`FR-QA-001~006`、`FR-STREAM-001~005`、`FR-AGENT-001~010`（详见 AGENT_SPEC §2）

### 导出与审计

`FR-EXPORT-001~003`、`FR-AUDIT-001~003`

### 非功能

`NFR-CAP-*`、`NFR-PERF-*`、`NFR-QUAL-*`、`NFR-SEC-*`、`NFR-OBS-*`、`NFR-DR-*`、`NFR-UX-*`

### 阶段门禁

`GATE-P0-001~008`、`GATE-P1-001~004`

---

## 附录 B：API、错误码与事件索引

### B.1 错误码

| 错误码 | 含义 | retryable |
|---|---|---|
| `AUTH_INVALID_CREDENTIALS` | 账号或密码错误 | 否 |
| `AUTH_FORBIDDEN` | 无权限 | 否 |
| `RESOURCE_NOT_FOUND` | 资源不存在或不可见 | 否 |
| `RESOURCE_FORBIDDEN` | 资源无权访问 | 否 |
| `IDEMPOTENCY_CONFLICT` | 幂等键与已有请求冲突 | 否 |
| `UNSUPPORTED_EXTENSION` | 扩展名不支持 | 否 |
| `INVALID_FILE_SIGNATURE` | 文件签名不匹配 | 否 |
| `UNSUPPORTED_SCAN_PDF` | 扫描 PDF 暂不支持 | 否 |
| `ENCRYPTED_FILE` | 文件加密 | 否 |
| `CORRUPTED_FILE` | 文件损坏 | 否 |
| `RESOURCE_LIMIT` | 超出资源限制 | 否 |
| `EXTERNAL_LLM_NOT_ALLOWED` | 文档禁止外发 | 否 |
| `PROVIDER_TIMEOUT` | 供应商超时 | 是 |
| `PROVIDER_RATE_LIMITED` | 供应商限流 | 是 |
| `PROVIDER_TEMPORARY_ERROR` | 供应商临时错误 | 是 |
| `RUN_CANCELLED` | Run 已取消 | 否 |
| `RUN_TIMEOUT` | Run 超时 | 否或按策略 |
| `VERIFICATION_UNAVAILABLE` | Citation 校验不可用 | 否 |
| `EXPORT_EXPIRED` | 导出已过期 | 否 |

### B.2 事件

`run_started`、`stage`、`token`、`citation`、`warning`、`completed`、`uncertain`、`refused`、`failed`、`cancelled`。

### B.3 方法和状态

- 时间使用 ISO 8601 UTC；
- ID 使用不透明字符串；
- 所有错误带 `request_id`；
- 破坏性变更升级 API 版本或提供兼容窗口；
- 所有终态持久化。

---

## 附录 C：数据字典与状态枚举

### C.1 Scope

```text
scope_type ∈ {global, document}
scope_document_id: scope_type=document 时必填，否则为空
```

### C.2 Run 状态

```text
received, planning, retrieving, retrying, waiting_for_user,
resuming, drafting, verifying, answered, uncertain, refused,
failed, cancelled
```

### C.3 DocumentVersion 状态

```text
uploaded, queued, parsing, chunking, embedding, indexed, ready,
parse_failed, embed_failed, delete_pending, deleted, delete_failed
```

### C.4 IndexGeneration 状态

```text
building, validating, published, retired, failed
```

### C.5 ExportTask 状态

```text
requested, queued, generating, ready, failed, expired
```

---

## 附录 D：测试命名、Fixture 与目录建议

建议未来真实工程采用：

```text
spec/
  SPEC.md
  contracts/
    openapi.yaml
    sse.schema.json
    worker.schema.json
  fixtures/
    documents/
    golden-set/
    providers/
  scenarios/
    auth.feature
    ingestion.feature
    retrieval.feature
    qa.feature
    stream.feature
    export.feature
  acceptance/
    matrix.md

tests/
  unit/
  contract/
  integration/
  e2e/
  security/
  performance/
```

测试命名建议：

```text
test_<requirement_id>_<behavior>()
```

示例：

```text
test_FR_RAG_003_scope_cannot_expand()
test_FR_DOC_006_new_version_publishes_atomically()
test_FR_STREAM_003_reconnects_from_last_event_id()
```

Fixture 原则：

- 不在测试中依赖真实生产密钥；
- 供应商使用 Fake/Stub，另设供应商冒烟测试；
- Golden Set、文档样本和预期 Citation 版本化；
- 测试失败输出 `request_id/run_id/document_id` 等诊断字段，但不输出 Secret。

---

## 附录 E：ADR 与开放决策登记

| ID | 决策 | 默认 | Owner | 阻断性 | 产物 |
|---|---|---|---|---|---|
| `DR-001` | 外部模型数据区域/留存/训练/删除 | P0 前审批 | IT/法务/安全 | 上线 | 审批记录 |
| `DR-002` | BM25 vs Qdrant sparse | BM25 | 研发 | P1 | 对比报告 |
| `DR-003` | RPO/RTO | 24h/4h 初始值 | 运维 | 上线 | 恢复演练 |
| `DR-004` | Verifier 输入/模型/阈值 | P0 冻结 | 算法/业务 | 问答上线 | 评测报告 |
| `DR-005` | 共享知识库是否满足业务 | 仅低敏全员文档 | 业务 | 真实文档 | 准入规则 |
| `DR-006` | 真实业务种子 | 3~5 个问题 | 业务 | 影响角色卡 | 少样本 |
| `DR-007` | LiteLLM 或内置 Adapter | 服务端统一入口 | 后端 | P1 | 运行设计 |
| `DR-008` | 文件限制和保留期 | TBD-P0 | 运维/业务 | 上线 | 策略表 |
| `DR-009` | LangGraph 受控 ReAct 及只读工具/答案门禁 | accepted，未实现 | M00/M05 | 当前目标 | [ADR-009](progress/changes/20261002-M00-langgraph-react-baseline.md) |
| `DR-010` | Agent 调用/预算/观察/并发上限 | TBD-P0 | M05/M11 | 依赖预算的切片 | 实测与预算 Contract |
| `DR-011` | checkpoint 治理、租约及一致性/恢复 | 待 Contract/ADR | M03/M01/M11 | 持久恢复 | 迁移/策略/故障演练 |

---

## 附录 F：来源、历史冲突与原型差距

### F.1 来源

- 当前规范：本文件 SPEC-1.1、AGENT_SPEC-1.0 与 ADR-009；
- 历史工程来源：`技术方案GPT.md`；
- 历史产品与路线来源：`问枢Pivot-技术方案V2.md`（用户文件，保留，不独立决定当前架构）；
- 页面与交互：`问枢Pivot-A3门户设计.md`、`风格样稿/S3完整原型/README.md`；
- 选型和历史备选：`问枢Pivot-选型详解.md`。

### F.2 冲突处理

| 历史表述 | SPEC 当前口径 |
|---|---|
| 固定线性 RAG 主图、LangGraph extra 暂缓 | LangGraph StateGraph + 原生工具 ReAct，旧实现待迁移 |
| 自由多 Agent / 层级群聊 | 首版单受控 Agent、两个只读工具 |
| 从证据另生成 Claims 可背书任意模型 Markdown | 只渲染通过支持校验的结构化事实 |
| Run/EventLog 落库等于 Agent 可恢复 | 独立 checkpoint + 数据库认领 + 预算/副作用一致性 |
| A3 早段 MVP 9 页 | 前台 6 页 + 后台 4 页 = 10 页，`index.html` 不计入 |
| 证据面板常驻 | MVP 点击引用打开非常驻证据抽屉；V2 再考虑常驻面板 |
| 内网 HTTP+IP | 默认 HTTPS/VPN/反向代理；禁止公网裸露 |
| “全部决策已确认”但仍有待办 | 以 P0 闸门和 ADR 管理开放项 |
| S3 原型模拟登录/上传/导出 | 仅为 Mock，不能作为生产验收证据 |
| 原型删除文案“不可恢复” | 生产语义为软删、检索下线、异步清理 |

### F.3 当前原型与生产差距

生产实现必须补齐：真实 JWT/RBAC、用户和会话隔离、真实文件上传和解析、scope 检索过滤、文档版本/删除、SSE 重连/取消、Citation/导出/审计以及可执行 OpenAPI 和测试。原型仅作为 UI/交互回归基线。

---

## 结论

本 SPEC 的核心开发顺序是：

```text
先冻结契约和不变量
→ 先写失败测试
→ 实现最小领域逻辑
→ 接入容器和外部 Stub
→ 完成 API/E2E
→ 运行 Golden Set、安全、性能、恢复测试
→ 满足 P0/P1 门禁后再扩展能力
```

不可妥协的最小闭环：

```text
服务端授权
+ 单文档 scope 强制过滤
+ 文档版本原子发布
+ 任务幂等
+ Citation 可追溯
+ 无证据拒答
+ Verifier 失败安全降级
+ SSE 断线可恢复
+ 审计追加写
+ 备份恢复满足实测 RPO/RTO
```

# 问枢 Pivot 开发进度

进度文档不是需求源。需求以 [SPEC.md](SPEC.md) 为准。模块边界以 [MODULE_SPEC.md](MODULE_SPEC.md) 为准。

最后更新日期是 2026-10-24。仓库基线是 `95367b3`。

contract-v0.2、03-A 和 04-A v0.1.0 已经发布。03-E 的 Web 恢复已经实现。OpenBao 已经配置。ND-GAP-01 的后台路由已经实现。02-D 至 02-H，以及 03-B、03-C 和 03-D，已经提交。04-B 的结果提交和 04-C 的 checkpoint 框架已经提交，提交是 `bfe07da`。04-B 测试收尾（ND-AGENT-04 S1）已经完成：修复结果提交 UoW 的 `new_id` 缺参缺陷，端到端提交测试已纳入 CI 分组，并补齐四个故障场景测试。04-C 恢复逻辑（ND-AGENT-04 S2）已经完成：实现版本锁校验与恢复管理器，版本不兼容、未授权、已终态与超期一律拒绝恢复，并补齐 checkpoint 写入与状态加密接缝的测试。04-D 租约与 fencing（ND-AGENT-04 S3）已经完成：新增 run_leases 表与 LeaseManager，checkpoint 写入与结果提交均已接入 fencing 校验，过期接管后旧 token 的写入被拒。04-E 供应商尝试与预算对账（ND-AGENT-04 S4）已经完成：新增 provider_attempts 表与 BudgetLedger，预扣幂等且受 fencing 与预算上限约束，派发后未结算保持未对账，结算幂等且账本游标随每次变更同步。04-F 真实 PostgreSQL 故障测试（ND-AGENT-04 S5）已经完成：真实多进程故障矩阵五项全过，并发现且修复迁移在真实 PG 上静默半途落地的缺陷（嵌套 begin_transaction 提前提交外层事务），故障矩阵已接线 CI 强制执行。至此 ND-AGENT-04 五个切片全部完成；正式验收环境待 Owner 指定。LlamaIndex 集成 L1 已经完成：新增索引构建器与 PIVOT_RETRIEVAL_BACKEND 开关，QA 可选走 LlamaIndex 内存索引，默认仍为自研路径，文档搜索不变。内存索引是启动快照，运行期不随 ingest 更新，持久索引与同步在 L3。LlamaIndex 集成 L2 已经完成：同一金标集双路径对比，两路期望判定全部通过、标注命中率同为 1.0，55 例差异逐项登记并给出结论，切换说明已入库。差异结论与依赖 L4 转正的决定已经 Owner 于 2026-10-21 确认。LlamaIndex 集成 L3 已经完成：索引改为 Qdrant 持久集合（同集群独立集合），启动时校验维度与模型版本并再水化，入库与删除按文档级对账同步，一致性测试全过；LlamaIndex 后端暂要求进程内同步入库，与 celery 组合时启动拒绝。LlamaIndex 集成 L4 已经完成：默认检索后端切换为 LlamaIndex，两个 llama 包转入主依赖，worker 侧集合对账接通 celery 入库，全量基线已在新默认下迁移；自研问答路径保留一个发布周期作回滚，删除另行处理。至此 LlamaIndex 集成四片全部完成，终局形态为 LlamaIndex 管检索、LangGraph 管流程。默认路径 Golden Set 实测已经完成：合成集 v0.2 全部通过、企业集 v0.3 内容层全过且标注命中率 1.0，检索层无相关性下限的拒答限制已定性并记录在实测报告中。ND-AGENT-05 已立项推进（预算上限 10 元，先用随想测试模型）：S1（05-A）模型适配器全注入接线已完成，写死默认值与消息转换丢失工具结果两个缺陷一并修复，主备切换与统一尝试记账接缝就位。S2（05-B）live 冒烟已执行：DeepSeek 官方 deepseek-flash 三步全过（总用量 877 token），thinking 模式拒绝强制工具调用的约束已定性并记入证据；随想渠道聊天接口受其上游 502 影响未完成冒烟，备用模型小米 mimo-v2.6 的 live 冒烟待接入后补。S3（05-C）Agent Golden Set 已落地：智能体层金标集 v0.1 共 9 个场景（法规语料取自司法部法规库公开原文，内部数据为合成并标注），Fake 图回归 11 项全过，判定口径已为 05-D live 评测备好复用。S4（05-D）live 评测首轮已执行：thinking 开关两组各 9 场景均通过 7 个，安全断言全清，总费用约 0.17 元；主要缺陷为存在不相关证据时不拒答（检索无相关性下限在智能体层复现），单 Run 调用中位数 7.5 次已作 DR-010 输入。至此 ND-AGENT-05 四片全部落地，剩余备用模型冒烟、业务复核集重跑与生产冻结。ND-GAP-01 真实接线已经完成：问答计数改读持久化 Run 存储，并修复状态字段误读的潜伏崩溃；任务列表改读 celery_tasks 持久表，响应契约经 Owner 确认对齐前端 items 键名。分页参数仍 TBD-P0。GATE 仍然 unverified。ND-P0-03 真实全链 live 评测已合并（PR #26），默认问答路径补接重排，拒答缺口与嵌入模型无关的结论已经定性。端到端可用方案已立项（Owner 2026-10-23 批准），U1 管理后台文档上传入口已经完成：管理员可在网页上传文档并自动入库，问答免重启可见（U2）与 Agent 接线（W）随后推进。U2 运行期增量再水化已经完成：celery 模式下 API 运行索引在检索前按间隔与集合对账收敛，新入库文档数秒内可被问答检索，缺口消除。W1 问答引擎开关已经完成（ADR-013）：默认仍为确定性流水线，配置为 agent 时启动期组装智能体运行器（模型全注入、预算与评测基线一致），配置缺失在启动期报错；结局对接 Run 状态机与 SSE 为 W2。W2 结局对接已经完成：AgentQaExecutor 把图结局映射到 Run 状态机与 SSE，引用绑定按生产 writer 链接形状修复（此前声明到证据映射恒为空）。线三 A 至 C 已经完成（ADR-014）：检索层新增相关性门禁、候选池解耦与单文档配额，默认全关。线三 D 标定中发现并修复稠密检索腿潜伏缺陷（FR-RAG-009）：默认路径的稠密通道自 LlamaIndex 集成以来因 as_retriever 传参问题静默失效，检索实际为 BM25 单腿；已改走直接构造检索器并把稠密候选下界定为 0.0，L2、L4 与 ND-P0-03 三份证据已加更正节并按修复后口径复测（受控口径：合成 94 / 120、企业 67 / 120，内容召回口径见更正节），L2 原行为等价结论失效待线三 D 以真实嵌入复核。线三 D 标定与四组复跑已经完成：DR-010 候选为重排下限 0.3、稠密下限 0.65、候选池 12、单文档配额不启用。真实全链复跑下企业集升至 108 / 120（内容层 96 / 96、no_answer 12 / 12、泄漏清零），合成集 108 / 120。两项未达成并已定性：企业集 unauthorized 层是授权相邻内容处置问题（受限内容零泄漏，属答案层议题），合成集 multi_span 是重排器对合成词元文本打分噪声所致（企业集同层 12 / 12）。智能体层代理核查显示 ag-005、ag-006 的证据由 5 块收窄到 1 块但未归零，端到端翻正取决于答案层判定，建议与 05-D 业务复核集重跑合并立项。生产默认装配暂不改动，候选值随 DR-010 冻结接线。M 线上下文瘦身已经完成（FR-AGENT-011）：decide 外发副本对较早读取全文做观测掩盖（最近一次保留全文，落库状态不变）、重复读短路（全文仍在外发历史中才短路，被掩盖证据再读直接给全文）、预算软触发开关（默认关，数值属 DR-010）；金标集新增 ag-010 重复读场景。live 验收五次运行后对账：修复后 thinking 开、关两组均 7 / 9 与基线持平（通过率达成）；端到端 token 降幅未测得（总量由触顶场景的轮换主导，机制级节省由单测确定性断言），详见 evidence/agent-m05/nd-agent-m-context-slimming.md。答案层相关性判定已经完成（FR-AGENT-012，ADR-015）：收尾成答前用一次模型调用判定问题与证据的语义相关性，不相关则复用 insufficient_evidence 拒答，判定调用计入单 Run 预算，异常与预算耗尽 fail-open；图层默认关，生产装配未接线（随 W3 与 DR-010 定）。live 验收三轮加定向探针：ag-005 与 ag-006 均被判定翻正（基线失败形态为照答），关闭组 8 / 9、开启组第 2 轮 7 / 9，安全断言全清且无误拒；证据无法满足模型时在决策循环内耗尽预算的新形态已定性（走不到收尾，判定无从介入），处置在循环与预算层。详见 evidence/agent-m05/nd-agent-012-relevance-gate.md。P1-1 多部门库隔离已经完成。方案见 ADR-016。S1 落库模型与迁移。S2 落可见库与检索过滤。S3 落按库分集合。S4 落管理 API 与审计。真实 PG 覆盖补进 db_pg 组。切片合入 PR #39 至 PR #44。SPEC 的 FR-RBAC-004 注记已翻为已启用。P1-2 输入清单见收尾记录。残留见收尾记录未决事项。原生问答路径删除已经完成（ADR-020）：问答桥与原生兜底已删，无 qdrant 时启动期报错；文档搜索与向量 dense 腿保留；测试与开发切 qdrant，CI 不新增服务容器。P1-2 S1 模型与迁移已经完成（ADR-017）：迁移 921f033d5987 落 memberships.expires_at 与 document_exceptions 表，端口与 PG、内存两路目录已接线，行为未改，可见性、授权与上传均未动，迁移、模型、SQLite 目录与真实 PG 共 15 项新测全过。P1-2 S2 临时授权已经完成（ADR-017）：读取时过期判定、续期走角色变更路径并写续期审计事件、过期行懒清理、60 天上限只管项目负责人一级（P1-4 前不可观测），单测、SQLite 目录与 HTTP 端点新测 15 项全过，真实 PG 组留 CI（本机无 PG 服务）。P1-2 S3 文档级例外已经完成（ADR-017）：个人与部门目标授予撤销、部门目标动态展开、同一例外集合打通授权钩子、检索选择与搜索过滤、授予去重为更新原行，服务与授权单测、检索、过滤搜索、SQLite 目录与 HTTP 端点新测 33 项全过，真实 PG 组留 CI（本机无 PG 服务）。P1-2 S4 审计同事务加固已经完成（ADR-017 D4）：PG 路径上部门、成员、认领、授予、撤销变更与审计写入共享同一数据库会话事务，审计失败则整个事务回滚、操作被拒绝，不留半截状态；内存路径保留补偿行为；角色变更加续期双事件同事务，S2 残留闭合；SQLite 目录新测 10 项全过，真实 PG 组留 CI（本机无 PG 服务）。P1-2 S5 上传门禁与认领同步已经完成（ADR-017 D5、D3）：上传门禁放宽给编辑与部门管理员，纯读者与无成员仍不可上传，上传仍默认落未分配库；认领提交后触发 worker 认领同步任务（celery 有界重试，最终失败写 authz.library.sync_failed，目标部门审计视图可见），同步完成前检索只滞后不越权；服务层门禁、HTTP 矩阵、提交器、HTTP 派发、检索滞后、SQLite 目录新测全过，真实 PG 组留 CI（本机无 PG 服务）。P1-4 S1 模型与迁移已经完成（ADR-018 D3、D4）：迁移 67fd19930bb8 落 libraries kind CHECK 加 project、folders 与 folder_memberships 表、documents.folder_id（空即默认文件夹，存量行无须迁移）；项目库所属部门走现有 dept_id 列；文件夹与项目成员角色值落模型（full/editor/reader、project_lead/editor/reader），权限判定由 S2 落；集合命名落到函数一级，检索接线由 S2 落；启动集合数触发条件经检查代码里不存在，未发明；迁移、SQLite 模型与命名新测全过，真实 PG 组留 CI（本机无 PG 服务）。P1-4 S2 文件夹管理已经完成（ADR-018 D3、D2）：部门管理员建删文件夹与成员管理、全权/编辑/只读三档、部门管理员本部门全权旁路、非空不删与删集合、双侧移动与认领同步复用、可见文件夹集合检索与例外共存、实时文件夹事实授权钩子、folder.* 审计与 PG 同事务；搜索复核为文档级闭包（无行命中 defer、有行严格判定、不查版本 currency，QA 钩子仍严格）；服务、授权、检索、集合、HTTP、SQLite、搜索复核新测 73 项全过，真实 PG 4 项留 CI（本机无 PG 服务）。P1-4 S3 项目库已经完成（ADR-018 D4、D2）：新迁移 6e6b5ec79a1c 把 memberships CHECK 扩为含 project_lead（Owner 批准并入 S3）；所属部门管理员建库与任命负责人、负责人管成员与 60 天上限接线、可见性并集与所属部门管理员分支、认领进项目、非空不撤、project.* 审计；服务、授权、检索、迁移、SQLite 目录与 HTTP 新测全过，真实 PG 2 项留 CI（本机无 PG 服务）；负责人越限经 HTTP 映射为 422（GRANT_EXPIRY_INVALID）。P1-4 S4 项目内文件夹与审计收口已经完成（ADR-018 D3、D4、D6）：项目内文件夹与 S2 同一套机制、管理方改为项目负责人（建删、成员三档、移动、非空不删、空删先删集合、检索按文件夹集合过滤、授权钩子实时复核、folder.* 审计）；visible_folder_ids 与 folder_visible 的部门管理员分支覆盖所属部门项目库、负责人见自己项目全部文件夹；新增负责人审计视图（按 project_id 过滤），部门视图按 dept_id 拾取本部门项目事件；永久授予复核清单覆盖项目文档例外；负责人对文件夹成员同样受 60 天上限与禁授永久约束（HTTP 422）；无新迁移，alembic 单头仍为 6e6b5ec79a1c；服务、授权、检索、SQLite 目录与 HTTP 新测全过，真实 PG 3 项留 CI（本机无 PG 服务）。至此 P1-4 四片全部完成，P1-3 实现随后。P1-3 S1 模型与迁移已经完成（ADR-019）：新迁移 c8842fce3b98 落 approval_requests 与 move_requests 两表（含 reconcile_status 与 reconcile_attempts）、版本状态机加 pending_approval 与 rejected 两态四条转移、端口与 PG、内存两路目录接线；未决唯一性走部分唯一索引（每文档每种请求最多一个 pending 行）；行为零改动，新态无生产入口；迁移、状态机、SQLite 目录与内存目录新测全过，真实 PG 组留 CI（本机无 PG 服务）。P1-3 S2 发布审批已经完成（ADR-019 D1、D6）：新增 ApprovalService 与 /api/v1/approvals 路由（批准、拒绝理由选填、撤回、重提、队列查询、复核读）；审批人按目标库 kind 定（部门→本部门管理员、公共→总管理员、项目→项目负责人），总管理员在部门/项目队列上行动另记代批事件、批公共库队列为普通批准；批准顺序为请求关闭→库改写→版本到 uploaded→作用域外触发 ingest，撤回即触发 ingest；复核读走专用隔离读路径（quarantine/{文档}/{版本}，每次读记 doc.approval.review，写入口径留给 S3）；PG 路径决策与库改写同事务；本片抓修 SqlAlchemyVersionStore.save 直用 UnitOfWork 致共享作用域内提前提交的生产缺陷（已改 write_scope）；服务、fail-closed、HTTP、SQLite 目录新测全过，真实 PG 3 项留 CI（本机无 PG 服务）；无新迁移，alembic 单头仍为 c8842fce3b98。PG 例外授权缺口修绿单已经完成：_LibraryBackedCatalog 补例外四读代理，S3 遗留的 PG 路径例外静默失效闭合；单测 3 项全过，真实 PG 1 项留 CI（本机无 PG 服务）。

SPEC-1.1、AGENT-SPEC-1.0 和 ADR-009 已经接受 LangGraph 受控 ReAct。Agent 端到端闭环已有 Fake 测试，覆盖 Phase 0 至 Phase 3。工具循环已经接入。04-A 持久化契约已经发布，采用 PostgreSQL、Fenced Saver 和 OpenBao。04-B 和 04-C 的框架已经入库。真实 PostgreSQL 恢复尚未验收。

ND-AGENT-01 已经修复答案一致性、引用绑定、支持门禁，以及校验前草稿泄漏。策略是保守的完整原文匹配。02-A、02-B 和 02-C 的内部契约已经发布，版本是 0.1.0。03-A 的恢复契约已经发布为 contract-v0.2。DR-010 尚未关闭，生产运行许可仍是 `TBD-P0`。

02-C 已有 Windows 候选、Linux 候选和 Ubuntu Hosted CI 技术验证。正式角色锁、构建和安全签认仍然 pending。架构 accepted 或 released，不等于 verified。

当前是 MODULE-SPEC-1.2 主线开发。Wave 3 夹具已经收口。ingest 和检索可以共用注入的 HTTP Embedding。HTTP Draft Writer 和 MinerU 云解析器可以注入。`PIVOT_PARSER=native` 可以装配 PyMuPDF、docx、pptx 和 xlsx。缺省仍是启发式解析和标准库。

dev-staging 的 Compose overlay 已经入库。ECS apply 仍等待 Owner 提供 SSH、安全组和磁盘。hashed refresh、Conversation 和 Run 可以跨装配。SSE 长连接和 Playwright 十页都是 opt-in。企业 Golden Set v0.3 有 120 条脱敏摘录。它不是业务复核，也不是 GATE。

工作区只使用 `Pivot/` 的 `main`。`wave-3-integrated` 只表示夹具收口，不等于 P0 通过。该标签覆盖 HTTP、composition root、Next 反代、存储客户端、Golden Set、Compose 和 opt-in 夹具。GATE-P0 全部 unverified。

## 1. 新会话恢复入口

1. 确认当前目录是 Linux 仓库 `/home/lumina888/Projects/Pivot`，分支是 `main`。`E:/AI Project/Pivot` 是历史 Windows 路径。不要进入 `../Pivot-Mxx-*`。
2. 读取 `AGENTS.md`。
3. 读取 `MODULE_SPEC.md`。
4. 读取本文件，以及本切片涉及的 `progress/modules/Mxx.md`。
5. 用 `git log --oneline --decorate -20` 确认实际基线。
6. 开发计划和工单见 [next-dev-spec.md](progress/next-dev-spec.md)、[tickets.md](progress/tickets.md) 和 [剩余 Tickets](progress/tickets/spec-1.1-remaining.md)。它们不是需求源。以各文件顶部索引为准。下文的 review 记录是历史。Owner 的历史环境范围见 [dev-staging 范围](progress/changes/20260910-M00-dev-staging-scope.md)。

本机入口见 [Linux runbook](ops/runbook-local-linux.md) 和 [2026-10-03 环境证据](evidence/local-linux-20261003.md)。Python 3.12.10、Node、npm、现有 extras、Playwright，以及 loopback 上的 API 和 Web，可以运行。Docker 的 daemon 和组权限已经配置。真实依赖镜像和代理授权尚未完成。memory 模式的 readyz 是 503，检索为空。这不表示真实存储或 RAG 就绪。GATE 保持未关闭。

当前下一刀是 04-C 的后续，以及 04-D 至 04-F。清单见 [下一步](evidence/agent-m03/nd-agent-04-next-steps.md)。02-A、02-B、02-C、03-A 和 04-A 已经发布。

下面从 2026-10-06 的审批记录开始，都是历史执行记录。其中的“待签认”和“0 ready / 5 review / 24 blocked”不是当前状态。已完成的候选 CI 不重复安排。

2026-10-06 Owner 授权的[真实供应商直连探针](evidence/wave3-m11/live-api-smoke-20261006.md)：仅合成样本，共 10 次有界业务 API 请求，无自动重试/故障转移；Qwen/GPT/Grok 原生工具调用结构通过，embedding 返回 1024 维有限向量，rerank 顺序通过；Qwen 强制工具请求需关闭思考模式，本轮对照默认行为为 400；MinerU 提交 401，无文件上传/解析任务。私有准备模板保留且 Git-ignored/mode600，未改业务接线或自动加载；既有私有配置安全回归 22 passed/1 skipped。Owner 要求本轮直接调用、不实施计费；未核算实扣或实现 10 元硬封顶，不能当生产预算批准。Owner 确认更新 MinerU Token 后增加 1 次提交复测（累计 11 次业务 API 请求），仍返回 401；Token 字段非空/唯一，无重复 Bearer、内部空白或混用其他供应商凭据，未证明有效性或是否确实换值。Owner 随后确认刚创建且已启用；增加 1 次随机不存在批次的只读 GET，同样 401 / `user authenticate failed`，累计 12 次认证 API 尝试（含该只读诊断）。当前值无明显掩码/占位符；官方前端确认 v4 Bearer 与创建弹窗完整复制方式，非可解码 JWT 不证明格式错误。无新提交/上传/解析任务，Owner 确认完整复制来源后增加 1 次独立 curl 只读对照（显式禁用代理/正常 TLS），同样认证 401，累计 13 次认证尝试（含 2 次只读诊断），无新提交/上传/重试；进程/模板无显式代理/自定义 CA。Owner 随后询问 Access Key ID/Secret Access Key，下一步确认字段所属服务页面与凭据类型，不将签名密钥替代 Bearer Token；根因未确定，不自动重试或切换无 Token 的轻量接口；这些直连探针不等于应用端到端/ReAct/GATE 验收，签认、DR、DoR 和 0 ready/5 review/24 blocked 均不变。

上述 MinerU 401 的最新跟进：Owner 确认此前来自 OpenXLab SSO 密钥管理，经指引转到 MinerU API Token 页面后更新本地字段；新只读查询 HTTP200/code -60012，`vlm` 真实直连提交/一页合成 PDF 上传/7 次状态轮询/ZIP 下载/`full.md` 标记验证均通过，无重试。本轮 9 次认证 API + 2 次不带 Token 的存储请求，累计 22 次认证尝试。当前供应商认证/解析阻断已解除，历史失败保留；不证明应用装配、完整 ingest 或 ReAct。本轮探针没有沿用既有适配器向存储调用传 API 授权头的行为；该缺陷已在后续 [TDD 修复](evidence/wave3-m11/mineru-storage-credentials.md) 中隔离：上传/下载传空头，提交/轮询保持认证。同域/异域签名 URL 四用例分别 Red→Green，MinerU 单元20 passed，相关 Worker/装配/私有配置/安全组238 passed/1 skipped；改动 Ruff/compileall/主动 LSP通过。未新增live调用或修改私有配置，应用适配器live及完整Agent验收仍待；存储域名/重定向/归档资源策略未在此扩展。生产契约/DR/DoR/GATE 与票状态均不变。

此前 [02-C 隐藏目录证据上传修正](evidence/agent-m03/nd-agent-02-c/hidden-artifacts.md)：固定 upload-artifact 默认排除隐藏目录，而 trial 位于 `.pi/`；显式启用隐藏目录读取，保留本次 trial 顶层 JSON/log/txt 非递归白名单，不上传配置/wheel/venv。既有上传契约 Red1 failed→安全组128 passed；完整Python重跑 **1031 passed/19 skipped/0 failed**、harness exit0、ruff/compileall与改动Python/YAML主动LSP通过。首次180秒工具等待超时且无遗留进程，第二次420秒上限完整通过。未推送/dispatch/验证Hosted上传；02-C review、0 ready/5 review/24 blocked与所有签认/DR/GATE不变，下一步仍须Owner审查待验证ref并批准远端手动CI。

此前 [02-C Ubuntu 手动候选 CI 入口准备](evidence/agent-m03/nd-agent-02-c/ubuntu-ci-preparation.md)：新增仅手动确认触发的 Ubuntu24.04/Python3.12.10 验证流程，Actions 固定 commit、隔离 driver/native resolver/双离线重建/哈希负向/20技术探针与旧回归；准备工具严格拒绝平台/材料漂移、非官方URL、畸形JSON及越界/旧输出。新增61项本地检查，安全组128 passed；原环境完整Python **1031 passed/19 skipped/0 failed**、harness exit0、ruff/compileall通过，工具/测试/YAML主动LSP clean。本机Arch前检正确拒绝且无输出，主.venv未装LangGraph。未推送或触发Hosted CI，默认ci.yml/正式依赖/既有候选/业务不变；02-C review、0 ready/5 review/24 blocked、所有签认/DR/GATE不变。下一步经Owner审查后在远端运行手动CI并归档真实证据，不把入口准备当CI passed。

此前 [02-C压缩wheel错误脱敏回归](evidence/agent-m03/nd-agent-02-c/compression-errors.md)：修复离线核验工具未捕获DEFLATE/LZMA底层解压异常、CLI泄漏traceback/本机路径的问题，沿用既有脱敏分类。新增三种压缩格式9项正负向测试，Red4 failed/5 passed后安全组67 passed；原环境完整Python**970 passed/19 skipped/0 failed**、harness exit0、ruff/compileall与两Python文件主动LSP clean。Windows111项材料、bookworm/Ubuntu各109个缓存wheel复核通过；未改业务/依赖/锁/CI/用户配置，未重跑目标候选/正式CI/Web/PG/live。02-C review、0 ready/5 review/24 blocked及签认/DR/GATE不变，下一步仍须前置提案签认与批准验证环境。

此前 [02-C离线候选一致性工具](evidence/agent-m03/nd-agent-02-c/integrity-tool.md)：`ops/check_candidate_integrity.py`严格核验manifest/锁集合、文本摘要、固定项目输入和可选wheel字节/METADATA，拒绝重复项/越界路径，CLI错误脱敏且明确不等于批准。Windows manifest补齐锁文件名（版本/哈希不变）；Windows111项材料、bookworm/Ubuntu各109个缓存wheel复核通过。新增56项安全测试，原环境完整Python**961 passed/19 skipped/0 failed**、ruff/compileall与两Python文件主动LSP clean。未改业务/依赖/锁/CI/用户配置，未重跑目标候选/正式CI/Web/PG/live；02-C review、0 ready/5 review/24 blocked、所有签认/DR/GATE不变。

此前 [02-C公开供应链诊断](evidence/agent-m03/nd-agent-02-c/supply-chain-public-check.md)：Ubuntu/bookworm109个包名/版本集合一致，OSV batch未返回命中、已知漏洞正/负对照通过；只作数据库快照，不称零漏洞或安全签认。grpcio-tools/langsmith源码hash/身份核验后补充对应上游版本标签主LICENSE全文、commit/blob/静态版本绑定，wheel缺文本仍保留。原项目Python**905 passed/19 skipped/0 failed**、ruff/compileall通过；未改依赖/业务/CI或发送项目数据。正式CI/角色锁/许可证兼容/CVE/遥测/原生库与所有签认仍pending，业务DoR/DR/GATE不变。

此前 [M11 私有配置回归修正](evidence/wave3-m11/private-env-regression.md)：staging测试改为验证Git索引及仓库实际忽略规则，允许正常本地配置存在，不读删用户`.env`。新增9项临时仓库负向/正向用例；本机完整Python分组**905 passed/19 skipped/0 failed**，ruff/compileall通过。测试要求Git及工作区元数据；未重跑候选容器/正式Ubuntu CI，不解除Agent签认或GATE。

此前 [Ubuntu 独立候选锁验证](evidence/agent-m03/nd-agent-02-c/linux-ubuntu.md)：在新容器/目录原生重新解析109 wheel，逐字节核验已有缓存后完成双venv离线hashes安装/pip check、错误哈希负向与技术探针各20 passed。完整Python分组895 passed/1 failed/19 skipped、ruff/compileall通过；唯一失败仍是根`.env`存在性断言，未读删配置或放宽测试。已提交独立proposed锁/含源码工具链来源的manifest；Ubuntu源码诊断不等于Actions artifact/Hosted CI，正式CI/角色锁/供应链/签认仍pending，不解锁业务。

上轮 [清华源 Ubuntu 诊断](evidence/agent-m03/nd-agent-02-c/linux-ubuntu-tuna.md)：Python3.12.10源码20.5MB/3.4秒下载，摘要与官方HTTPS Sigstore bundle相符（未做完整签名链验证）；Ubuntu24.04/glibc2.39源码构建、stdlib与pip25.0.1验证通过，清华pip原生dry-run解析109个wheel，版本/报告哈希与bookworm差异0。仅临时容器配置清华apt/pip；未装Agent依赖，未做独立Ubuntu锁/双重建/探针/Hosted CI，不代签或解锁业务。

02-C 新增 [离线供应链材料与 Ubuntu 下载阻断](evidence/agent-m03/nd-agent-02-c/supply-chain.md)：109 个 bookworm wheel 哈希/身份相符、107 个检出随包许可证文本，2 个待补齐；许可证兼容性/CVE/遥测仍 pending。Ubuntu 镜像可运行，但固定 Python 构建连续下载超时，未生成 Ubuntu 锁，不解除业务 DoR。

当前跟进见 [02-A/B/C 审核与待签清单](evidence/agent-m03/nd-agent-02-abc-review.md)：预算 draft.2 映射已修订但未批准。Debian bookworm runtime 候选锁已验证（109 wheel、双环境 20 probes、895/1/19），见 [证据](evidence/agent-m03/nd-agent-02-c/linux-bookworm.md)；Ubuntu CI、供应链与签认仍 pending，执行单见 [原生验证单](evidence/agent-m03/nd-agent-02-c/linux-validation.md)。**02-A/B/C review、02-D～H blocked 不变**，技术验证不能代签各消费者/Owner。

如果没有指定切片：优先 **04-C~F 持久化实施**（Checkpointer/租约/预算账本/故障测试，约 2 周）或 **02-A/B/C 最终签认与依赖锁发布**；**04-B Claims/Citation/Message/终态事务与 outbox 已完成**（Phase 1-4: 数据库模型/Repository/UoW/Dispatcher，Phase 5 测试部分完成）；[证据](evidence/agent-m03/nd-agent-04-b.md)；02-A [内部模型/工具/State 提案](progress/changes/20261002-M05-agent-internal-contract.md)、02-B [预算提案](progress/changes/20261002-M05-agent-budget-contract.md) 已发布为 AGENT-INTERNAL 0.1.0 / AGENT-BUDGET 0.1.0；02-C [依赖/锁定申请](progress/changes/20261002-M03-agent-dependencies-lock.md) 已发布为 AGENT-DEPENDENCIES 0.1.0。03-A [恢复Contract](progress/changes/20261003-M00-agent-resume-contract.md) 已发布为 AGENT-RESUME 0.2.0 / contract-v0.2；[证据](evidence/agent-m00/nd-agent-03-a.md)。03-E [Web恢复UI](evidence/agent-m05/nd-agent-03-e.md) 与 [M09 UI](evidence/agent-m09/nd-agent-03-e-ui.md) 已完成。04-A [checkpoint/租约/事实/outbox](progress/changes/20261003-M03-agent-persistence-contract.md) 已批准并发布为 AGENT-PERSISTENCE 0.1.0；[证据](evidence/agent-m03/nd-agent-04-a.md)；[签认](progress/approvals/20261012-04-a-approved.md)；OpenBao 密钥管理已配置（docker/openbao/）。下一步 04-C~F 实施（Checkpointer/租约/预算/故障测试）；ND-AGENT-02~05父票实施中。ND-AGENT-01 done，证据见 `evidence/agent-m05/nd-agent-01.md`。先读 `spec/AGENT_SPEC.md` 和 ADR-009。旧 ECS apply/live 检索工单保留，不覆盖 Agent 关键路径。企业 Golden Set v0.3 已填 120 条脱敏摘录，**不等于**业务复核或 GATE-P0-002。Wave 3 夹具已收口（`wave-3-integrated` **不等于** P0 通过）。不要冻结 `TBD-P0`，不要把 Fake HTTP / 存储客户端 / 合成 Golden Set / 企业 Golden Set 空 schema / Fake embedder / stdlib BM25 / 进程内压测/恢复 / Dockerfile fixture / opt-in 100k Fake retrieve / Compose web/worker 文件 / Fake ingest upsert / 进程内 HTTP ingest / 可注入限流计数 / sqlite 文档事实 / sqlite 导出任务 / sqlite refresh/会话 / sqlite Run/EventLog / eager Celery / Compose Celery fixture / Fake MinIO worker ingest / Compose api 共享存储注入 / Fake worker Qdrant upsert / Compose api celery 注入 / Compose Qdrant·Redis 注入 / Compose 登录限流注入 / Wave 3 夹具收口 / ingest 共用 HTTP Embedding / Fake HTTP Writer / Fake MinerU 解析器 / staging Compose overlay / SSE 长连接夹具 / 真实解析库 extra / opt-in Playwright 十页 标成 GATE verified。不要新建 worktree。

### 2026-10-06 02-B draft.3 调用硬门禁与图熔断分工

Owner 对“实际调用负责硬预算，图步数负责防循环”回复“同意”，记录 [OWNER-02-B-GRAPH-20261006](progress/approvals/20261006-02-b-call-graph-separation.md)，输入 `e06fb6f`。02-B提案及拟议policy升draft.3，移除未发布graph_supersteps_max，精确逐super-step原子账本不再是收费门禁前置；所有收费action/attempt仍执行前预留、累计恢复对账，无收费循环仍受有限时限/取消/熔断和禁止无限自动重入。未改公开契约、业务、依赖或迁移；期限语义下一项确认，整份提案/消费者/额度/运行许可pending。0 ready/5 review/24 blocked、DR/TBD/GATE不变；以下早先确认/验证为历史记录，不能验收draft.3运行时。本轮验证：2schema/4正向/81负向、settlement/其他示例值/期限条款不变；既有契约283及QA/Run/SSE79、合计362 passed；10文档/206本地链接/29票状态及Markdown/diff检查通过，命令与限制见M05本轮进度。

### 2026-10-06 02-B Owner 严格费用控制方向确认

用户最终回复“那就严格费用把控方向”，已记录 [OWNER-02-B-COST-20261006](progress/approvals/20261006-02-b-strict-cost-direction.md)，输入 `edc962f`。仅选择执行前预留可信费用上界/返回后结算/unknown保留预留/不可验证时停止收费调用，所有收费角色（含PR-01）与恢复共用累计账本。具体额度、图步数及执行/澄清期限语义另行决定；未修改对应schema或批准整份02-B/运行许可。仍 **0 ready / 5 review / 24 blocked**；02-A既有批准及02-C/03-A/04-A状态不变，DR/TBD/GATE不变。本轮仅文档记录，不改业务或运行配置。

### 2026-10-06 02-A Owner 单项设计批准

Owner 在本会话对“02-A 原提案及 PR-01 补充”明确回复“同意”，已记录 [OWNER-02-A-20261006](progress/approvals/20261006-02-a-owner-design.md)，批准输入 `32dd4e7`。仅设计方向生效，消费者签认/契约发布和实施 DoR 仍待完成；02-A 保持 review，其他四项待签认，仍 **0 ready / 5 review / 24 blocked**。本轮只记录批准及同步入口，不修改既有未填写确认模板、业务、依赖或运行配置。以下为该补充提出时的设计/验证记录，不表示 Owner 仍未确认。

### 本轮 02-A 单项审阅补充：PR-01 用户输入 Prompt 重写

按 Owner 要求，在 [02-A 提案 §3.4](progress/changes/20261002-M05-agent-internal-contract.md#34-用户输入-prompt-重写pr-01追加待审核)追加 PR-01 待审设计：保留原始意图/约束与原始消息/幂等依据，重写请求不改变授权或外发资格；模型重写调用纳入同一累计预算，检索 query rewrite≤2 与澄清≤1 不变。新增三组运行时 Red 设计，未实现或运行该能力；补充前的形状/技术证据不覆盖 PR-01。后续 02-A 签认须明确包含该补充，不视为已批准 02-B/C、03-A、04-A；仍 **0 ready / 5 review / 24 blocked**，DR/TBD/GATE 不变。验证：既有契约283/QA与Run与SSE79、合计362 passed；首次混组的5项conftest导入冲突拆组后通过；4文档/81本地文件链接/4JSON块与Markdown/diff检查通过。[命令及限制](progress/modules/M05.md#本轮-02-a-单项审阅pr-01-用户输入-prompt-重写)。

## 2. 当前波次与模块状态

状态枚举：`planned` → `claimed` → `in_progress` → `blocked` → `review` → `integrated`。主线会话可更新本表。

| 模块 | 状态 | 代码位置 | 基线契约 | 最近证据 | 下一步 |
|---|---|---|---|---|---|
| M00 契约治理 | in_progress | `main` | 目标 SPEC-1.1；发布 contract-v0.1 | 公共契约48 passed；03-A schema62/04-A schema173 passed；5前置review | 消费者签认；Linux/预算映射；04-A治理审核 |
| M01 身份授权 | integrated | `main`（tag `M01-v0.6.0`） | `contract-v0.1` | 37 单元/安全 + 登录/改密/管理用户 HTTP + PATCH 角色/重置 + Compose 注入 Redis 限流 + refresh 跨装配；ND-GAP-03 首次改密落库与服务端强制已合并（PR #22） | 人工标注 Golden Set 或 STG-04 ECS apply |
| M02 文档接入 | integrated | `main`（tag 目标 `M02-v0.6.0`） | `contract-v0.1` | 27 单元 + 上传/列表/详情/重试/删除/预览/下载 HTTP；runtime 上传后进程内 ingest；`PIVOT_INGEST=celery` 可入队；Compose api 注入 celery ingest；publish 写回 chunk | HTTP 缺省仍 sync ingest |
| M03 数据基础 | in_progress | `main`（旧 tag 目标 `M03-v0.8.0`） | `contract-v0.1`；依赖 draft proposed | 02-C Windows/Linux 原生候选与 Ubuntu Hosted CI 技术通过；04-A proposed/schema173 passed；旧 SQL 基线保留 | 角色锁/构建、供应链与依赖签认；04-A签认/DR-011/批准PG环境 |
| M04 检索 RAG | integrated | `main`（tag 目标 `M04-v0.5.0`） | `contract-v0.1` | 31 单元 + 搜索 HTTP + Qdrant dense + stdlib BM25 + ingest/检索共用注入 HTTP Embedding/bge + 合成 Golden Set 120 条 + 企业脱敏摘录 120 条 + ND-P0-03 live 全链评测（现有集） + U2 运行期增量再水化（celery 入库免重启可见） + 线三相关性门禁与单文档配额（ADR-014，默认全关，FR-RAG-008 七项） + 稠密检索腿修复与 0.0 候选下界（FR-RAG-009） + 线三 D 标定与复跑（DR-010 候选已登记） | DR-010 冻结与门禁候选值接线；答案层相关性判定立项；STG-04 ECS apply；ND-P0-03 复核集补跑待 ND-P0-01-A |
| M05 ReAct/QA/Run/SSE | in_progress | `main` | 目标 AGENT-SPEC-1.0；发布 contract-v0.1 | 02-D～H 开发实现；03-B 阶段投影 9 passed；03-C 取消 3 passed；03-D 图内澄清 4 passed；ND-AGENT-04 与 05 全片；W1 问答引擎开关与 Agent 生产装配（ADR-013）；W2 Agent 结局对接 Run 状态机与 SSE（FR-AGENT-008 三项，含收尾器生产形状映射修复）；M 线上下文瘦身（FR-AGENT-011 六项：观测掩盖、重复读短路、预算软触发）；答案层相关性判定（FR-AGENT-012 七项：不相关拒答、fail-open、判定计入预算、默认关） | W3 真实模型联调后定默认引擎；attempts 落账与澄清恢复执行待契约与持久化会话；03-E 仍等待 03-A 公开 resume；DR-010 待冻结 |
| M06 导出/审计 | integrated | `main`（tag 目标 `M06-v0.3.0`） | `contract-v0.1` | 26 单元 + 导出/审计 HTTP + PG 任务跨装配；ND-GAP-02 审计统一落库与分级失败已合并；ND-GAP-04 签名下载消费者与 ADR-012 管理员口径已合并（PR #23） | 公开入口 `/d/` 反代属部署事项（ND-STG-04-A） |
| M07 Worker/解析/索引 | integrated | `main`（tag `M07-v0.10.0`） | `contract-v0.1` | 79 单元 + ingest→Qdrant + HTTP 进程内 runner + parse 队列消费 + Celery eager ingest + Compose Celery worker + 共享 MinIO/PG runner + worker Qdrant IndexPublisher + ingest HTTP Embedding + MinerU 云解析器 + `worker[parse]` native extra | 缺省仍启发式；OCR 属 P2 |
| M08 Web 基础 | integrated | `main`（tag `M08-v0.3.0`） | `contract-v0.1` | M08 18 tests + SSE 去缓冲 Route Handler + typecheck/lint 通过 | Compose web 由 M11 装配 |
| M09 员工前台 | integrated | `main`（tag 目标 `M09-v0.2.0`） | `wave-1-integrated` | 13 Fake + followRunEvents + opt-in Playwright 十页 | Chrome/Edge 版本仍 TBD-P0 |
| M10 管理后台 | integrated | `main`（tag `M10-v0.1.0`） | `wave-1-integrated` | 9 Fake + 文档上传入口（U1） + opt-in Playwright 后台页 + `/admin/metrics` `/admin/tasks` HTTP（ND-GAP-01） | 指标与任务已读持久事实；分页仍 TBD-P0 |
| M11 集成/质量/运维 | in_progress | `main`（tag `M11-v0.25.0` / `wave-3-integrated`） | `wave-3-integrated` | 分组回归见本切片日志 | GATE-P0 仍全部 unverified；企业 Golden Set 为脱敏摘录诊断；staging ECS apply 待 Owner SSH/安全组/磁盘 |

模块详细状态由各自 `progress/modules/Mxx.md` 维护。历史 `../Pivot-Mxx-*` worktree 不再使用。

### 当前 Agent 改造

FR-AGENT-001~010 仍为 accepted、未完整实现/验收；FR-AGENT-005 的迁移基线答案门禁已修复（ND-AGENT-01 done），不代表事实持久化或真实图通过。02 因预算/依赖 Contract blocked，03 因恢复公开 Contract blocked，04 因 checkpoint/迁移策略 blocked，05 因前序闭环/批准 live 环境 blocked。不得以旧 integrated 状态或旧绿灯验收新需求；完整 Accountable/测试见 AGENT_SPEC 和验收矩阵。

## 3. 需求追踪摘要

完整映射和 Accountable/Contributors 见 [`MODULE_SPEC.md §8`](MODULE_SPEC.md#8-需求-accountable-映射)。验收链必须遵循：需求 ID → 场景 ID → 契约/数据 → 测试 ID → 验收证据 → verified。

| 需求范围 | Accountable | 测试/场景入口 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| FR-AUTH-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/`、`tests/integration/pipeline/test_FR_AUTH_001_http_login.py`、`tests/integration/pipeline/test_FR_AUTH_004_http_admin_users.py`、`tests/integration/pipeline/test_FR_AUTH_002_http_login_rate.py`、`tests/integration/pipeline/test_FR_AUTH_001_http_postgres_sessions.py` | implemented | 37 项单元/安全 + 登录/刷新/退出/改密/管理用户 HTTP；PATCH 角色/重置；限流计数可注入 Redis CacheStore；Compose api 注入阈值/窗口（不写死次数；进程外缺省不锁定）；`PIVOT_STORAGE=postgres` 时 hashed refresh 跨装配存活（CI sqlite） |
| FR-RBAC-001~004 | M01 | `tests/unit/auth/`、`tests/security/auth/`、`spec/scenarios/auth.feature`、`tests/integration/pipeline/test_FR_RBAC_002_http_conversations.py`、`tests/integration/pipeline/test_FR_RBAC_003_http_preview.py`、`tests/integration/pipeline/test_FR_AUTH_001_http_postgres_sessions.py` | implemented | 资源四重授权与会话隔离；会话 CRUD HTTP 仅 owner 可见；`PIVOT_STORAGE=postgres` 时 Conversation 跨装配存活（CI sqlite）；预览/下载按详情同等可见性；库隔离已启用（ADR-016）：文档归属唯一库，可见库取并集，检索与文档入口均按库授权，未授权按不存在处理；db_pg 组 16 项覆盖真实 PG |
| FR-DOC-001~008 | M02 | `tests/unit/documents/`、`tests/integration/pipeline/test_FR_DOC_001_http_upload.py`、`tests/integration/pipeline/test_FR_DOC_007_http_lifecycle.py`、`tests/integration/pipeline/test_FR_RBAC_003_http_preview.py`、`tests/unit/worker/test_FR_DOC_006_qdrant_index.py`、`tests/integration/pipeline/test_FR_DOC_006_ingest_qdrant.py`、`tests/integration/pipeline/test_FR_DOC_001_http_postgres_facts.py`、`tests/integration/pipeline/test_FR_DOC_005_celery_postgres.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_minio_ingest.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_qdrant_publish.py` | implemented | 28 项 M02 单元 + 文档上传/列表/详情/版本/重试/删除/预览/下载 HTTP；runtime 上传后进程内 ingest（信封仍 uploaded）；`PIVOT_INGEST=celery` 时可 eager 入队；Compose api 注入 celery ingest（yml 不写死 broker，CI 不 up）；`PIVOT_STORAGE=postgres` 时文档事实可跨装配存活（sqlite 测试 URL）；worker 可从共享 MinIO 读取对象字节（CI Fake client）；worker 可向注入 Qdrant 发布（CI Fake client） |
| FR-SEARCH-001~002 / FR-RAG-001~006 | M04 | `tests/unit/retrieval/`、`tests/security/retrieval/`、`tests/integration/pipeline/test_FR_SEARCH_001_http_search.py`、`tests/integration/pipeline/test_FR_SEARCH_001_qdrant_retrieval.py`、`tests/integration/pipeline/test_FR_RAG_001_bm25_runtime.py`、`tests/integration/pipeline/test_FR_RAG_001_http_embedding_bge.py`、`tests/integration/pipeline/test_FR_DOC_006_ingest_http_embedding.py`、`tests/integration/pipeline/test_NFR_QUAL_golden_set.py`、`tests/integration/pipeline/test_NFR_QUAL_golden_set_enterprise.py` | implemented | 31 项 M04 单元 + 搜索 HTTP + Qdrant dense + ingest 可写入同一端口 + stdlib BM25 + ingest/检索共用注入 HTTP Embedding/bge（CI Fake transport）+ 合成 Golden Set 120 条 + 企业脱敏摘录 120 条（Fake Keyword，非业务复核） |
| FR-QA-001~006 / FR-STREAM-001~005 | M05 | `tests/unit/qa/`、`tests/unit/runs/`、`tests/contract/stream/`、`tests/integration/pipeline/test_FR_STREAM_001_http_runs.py`、`tests/integration/pipeline/test_FR_STREAM_001_http_postgres_runs.py`、`tests/integration/pipeline/test_FR_STREAM_002_sse_live.py`、`tests/integration/pipeline/test_FR_RBAC_002_http_conversations.py`、`tests/integration/pipeline/test_FR_QA_001_http_writer.py`、`tests/e2e/test_agent_complete_flow.py` | in_progress（ND-AGENT-01 done；Phase 0-3 完成；新图/恢复/完整持久化待实现） | 79 项 M05 QA/Run/SSE + 4 项端到端测试（Fake 模型）；Agent 端到端闭环已完成：工具循环、预算门禁、结构化答案；新增 HTTP/SSE/消息/导出安全回归见 `test_FR_AGENT_005_answer_publication.py`；旧 30 项 M05 领域 + Run/SSE 长连接 + 会话 CRUD HTTP（消息由 Run 合成）；Conversation 与 Run/EventLog 可走 SQLAlchemy（CI sqlite）；Claim/Citation 仍不入库；`PIVOT_LLM=http` 可注入 Writer（CI Fake transport）；uvicorn 长连接 opt-in skip |
| FR-EXPORT-001~003 / FR-AUDIT-001~003 | M06 | `tests/unit/exports/`、`tests/unit/audit/`、`tests/security/export/`、`tests/integration/pipeline/test_FR_EXPORT_001_http_exports.py`、`tests/integration/pipeline/test_FR_EXPORT_001_http_postgres_tasks.py` | implemented | 26 项 M06 单元 + 导出/审计 HTTP；运行时导出字节可接 MinIO，公开 URL 仍为 signer；`PIVOT_STORAGE=postgres` 时任务可跨装配存活（sqlite 测试 URL） |
| §2 存储不变量 | M03 | `tests/integration/db/`、`api/src/pivot/db/`、`migrations/` | implemented | M03 数据测试 + 48 项 M00 契约回归通过；用户目录、文档事实、导出任务、hashed refresh、Conversation 与 Run/EventLog 默认 SQLite 覆盖；MinIO/Qdrant/Redis 默认内存 client；Compose 为 opt-in skip |
| §6 解析/分块/索引执行 | M07 | `tests/unit/worker/`、`tests/integration/pipeline/test_FR_DOC_006_ingest_qdrant.py`、`tests/integration/pipeline/test_FR_DOC_001_http_runtime_ingest.py`、`tests/integration/pipeline/test_NFR_OBS_compose_worker.py`、`tests/integration/pipeline/test_NFR_OBS_compose_api.py`、`tests/integration/pipeline/test_FR_DOC_005_celery_postgres.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_minio_ingest.py`、`tests/integration/pipeline/test_FR_DOC_006_worker_qdrant_publish.py`、`tests/integration/pipeline/test_FR_DOC_006_ingest_http_embedding.py`、`tests/integration/pipeline/test_FR_DOC_004_native_parser.py` | implemented | 79 项 M07 测试通过；stdlib/Fake 或注入 HTTP Embedding；可注入 MinerU 云解析器（CI Fake HTTP）；`PIVOT_PARSER=native` 可装配 PyMuPDF/docx/pptx/xlsx（`worker[parse]`；CI 微型夹具；缺 extra 失败闭环）；IndexPublisher 可写入注入 VectorStore；HTTP 上传默认可进程内 ingest；`PIVOT_INGEST=celery` 为 eager 任务（可见 PG version/task）；Compose api 注入 celery ingest（Dockerfile 装 worker[celery,parse]）；Compose worker 为注入 broker 的 Celery，只监听 parse 队列；worker 装配共享 MinIO/PG runner（CI sqlite + Fake MinIO）；`PIVOT_VECTOR_STORE=qdrant` 时 worker 装配 IndexPublisher（CI Fake client）；`PIVOT_EMBEDDING=http` 时 ingest 与检索共用注入 embedder（CI Fake HTTP）；`PIVOT_PARSER=mineru` 时装配云解析器（Compose api/worker 注入 `PIVOT_PARSER*`） |
| §1.5 / NFR-UX 设计系统与 client | M08 | `tests/e2e/fixtures/web/test-foundation.mjs` | implemented | M08 18 项基础测试通过（含 `/api/v1` rewrite 与 SSE 去缓冲 Route Handler）；产品页由 M09/M10 接管 |
| 前台 6 页 | M09 | `tests/e2e/user/test_user_web.mjs`、`tests/integration/pipeline/test_NFR_UX_browser_ten_pages.py` | implemented | 13 项 Fake fetch（含 followRunEvents）+ opt-in Playwright 十页；CI 默认 skip |
| 后台 4 页 | M10 | `tests/e2e/admin/test_admin_web.mjs`、`tests/integration/pipeline/test_NFR_UX_browser_ten_pages.py`、`tests/integration/pipeline/test_ND_GAP_01_admin_metrics_tasks.py` | implemented | 8 项 Fake fetch + opt-in Playwright 后台页；`/admin/metrics` `/admin/tasks` HTTP 已实现（ND-GAP-01，8 项集成测试）；指标与任务均已改读持久化事实，分页仍 TBD-P0 |
| NFR-CAP/PERF/OBS/DR、GATE-P0-001~008 | M11 | `tests/integration/pipeline/`、`tests/security/ops/`、`tests/performance/`、`evidence/wave2-m11/`、`evidence/wave3-m11/` | implemented（CI/Fake + HTTP + composition root + Next rewrite + opt-in Playwright 十页 + PG/MinIO/Qdrant/Redis + 合成 Golden Set + 导出 MinIO + 检索 dense 消费 Qdrant + ingest→Qdrant + 5 并发/进程内备份 + stdlib BM25 + Dockerfile/Compose api+web+worker + 100k opt-in + HTTP Embedding/bge Fake transport + ingest/检索共用 HTTP Embedding + Celery eager ingest + Compose Celery worker + worker 共享 MinIO/PG ingest + Compose api 共享 PG/MinIO + worker Qdrant IndexPublisher + Compose api celery ingest + Compose api/worker Qdrant/Redis + Compose api 登录限流注入 + Compose api/worker Embedding 注入 + 可注入 HTTP Draft Writer + 可注入 MinerU 云解析器 + `worker[parse]` native extra）；GATE-P0 unverified | TestClient；CI 不 build/up Compose、不跑 100k、不打真实供应商；Playwright/Compose/100k 默认 skip |

## 4. 当前波次计划

### Wave 0 — 基线冻结（已完成）

- [x] M00：从 SPEC §5、附录 B/C 建立并集成 `contract-v0.1` 草案（48 项契约测试通过）；
- [x] M03：建立数据对象、Repository/UoW 和 PG/MinIO/Qdrant/Redis adapter 接口草案；12 项 M03 测试与 48 项 M00 回归通过；
- [x] M08：建立 Next.js/TypeScript 工程、S3 设计系统和 API/SSE client 边界（9 项基础测试通过）；
- [x] Wave 0 退出评审：契约、数据接口、Web client 输入已冻结；三项所有权变更申请已批准；标签 `wave-0-integrated`。

### Wave 1 — 核心能力（已完成）

- [x] M01：认证会话、RBAC、资源四重授权（27 项测试，`M01-v0.1.0`）；
- [x] M02：文档签名、状态机、幂等与 tombstone（15 项测试，`M02-v0.1.0`）；
- [x] M07：可插拔解析/分块/Fake Embedding/索引代次（7 项测试，`M07-v0.1.0`）；
- [x] M04：服务端过滤、scope、RRF 降级（10 项测试，`M04-v0.1.0`）；
- [x] M05：问答主图、Run 幂等、SSE 事件日志（12 项测试，`M05-v0.1.0`）；
- [x] M06：导出授权/内容边界/过期与脱敏审计（26 项测试，`M06-v0.1.0`）；
- [x] Wave 1 退出评审：模块 tag 齐全；矩阵回填为单元层 `implemented`；M11 可装配单元/契约 fixture；标签 `wave-1-integrated`。

### Wave 2 — 页面与联调（已完成）

- [x] M09：员工前台六页、搜索带原问题、文档 scope、证据抽屉、拒答与导出入口（12 项测试，`M09-v0.1.0`）；
- [x] M10：管理后台四页、403、重试/删除、停用用户、审计脱敏（8 项测试，`M10-v0.1.0`）；
- [x] M11：分组 CI、进程内 Fake 认证→导出链路、Compose 意图与 Runbook 草稿（`M11-v0.1.0`）；
- [x] Wave 2 退出评审：三模块非快进合入；装配页测试适配；页面 Fake E2E 接入分组 CI；标签 `wave-2-integrated`。

### Wave 3 — P0/P1 门禁（夹具已收口；GATE 仍 unverified）

- [x] 依赖 Compose fixture：postgres / minio / qdrant / redis（钉镜像 + healthcheck + localhost；`M11-v0.2.0`）
- [x] Compose Postgres 的 opt-in Alembic 冒烟（默认 skip；`M11-v0.2.1`）
- [x] 应用 `/healthz` `/readyz`（TestClient 薄装配，`M11-v0.2.2`）
- [x] `/api/v1/auth/login|refresh|logout`（`M01-v0.2.0`）
- [x] `GET/POST /api/v1/documents`（`M02-v0.2.0`）
- [x] 文档详情/版本/重试/删除 HTTP（`M02-v0.3.0`）
- [x] `GET /api/v1/search`（`M04-v0.2.0`）
- [x] Run/SSE HTTP（`M05-v0.2.0`；EventLog 补发）
- [x] 导出/审计 HTTP（`M06-v0.2.0`；短时 URL，非对象字节下载）
- [x] 改密与管理员用户 HTTP（`M01-v0.3.0`；PATCH 仅 status）
- [x] PATCH 角色 / 重置密码 HTTP（ND-W3-07；`role` / `reset_password`）
- [x] 会话 CRUD HTTP（`M05-v0.3.0`；删除为隐藏，消息由 Run 合成）
- [x] 预览/下载 HTTP（`GET /documents/{id}/preview|download`；内存 Fake 对象字节）
- [x] composition root（`assemble_runtime_app`、Argon2id、memory 端口、`uvicorn pivot.http.main:app --factory`）
- [x] Next 反代 `/api/v1`（`PIVOT_API_ORIGIN` 注入 rewrite；浏览器仍同源）
- [x] opt-in Playwright 浏览器登录（`PIVOT_REQUIRE_PLAYWRIGHT=1`；CI 默认 skip）
- [x] opt-in Playwright 十页（ND-W3-10；前台 6 + 后台 4；CI 默认 skip；≠ GATE-P0-005）
- [x] PostgreSQL 用户事实源客户端（`SqlAlchemyUserDirectory`；`PIVOT_STORAGE=postgres`；URL 注入）
- [x] MinIO 文档对象客户端（`MinioObjectStore`；`PIVOT_OBJECT_STORE=minio`；endpoint/bucket 注入）
- [x] 导出对象接到 MinIO（`ExportObjectAdapter`；公开 URL 仍 `PublicDownloadSigner`）
- [x] Qdrant 向量客户端（`QdrantVectorStore`；`PIVOT_VECTOR_STORE=qdrant`；endpoint/collection 注入）
- [x] Redis 缓存/队列客户端（`RedisCacheStore`/`RedisQueueStore`；`PIVOT_CACHE_STORE`/`PIVOT_QUEUE_STORE=redis`；endpoint 注入）
- [x] Golden Set v0.1-synthetic 检索夹具（10 条分层，Fake KeywordRetriever）
- [x] Golden Set v0.2-synthetic 检索夹具（120 条分层，Fake KeywordRetriever；非企业标注）
- [x] 企业 Golden Set v0.3 脱敏摘录（ND-P0-01；120 条，十层各 12；Fake Keyword 诊断；≠ 业务复核；≠ GATE verified）
- [x] 检索 dense 路消费 Qdrant VectorStore（Fake query embedder；不冻结 k/距离）
- [x] 5 并发检索夹具与进程内事实备份/恢复（非 100k、非新 ECS）
- [x] stdlib BM25（注入 k1/b/分词）与可选 overlap/bm25 rerank（非 jieba/bge）
- [x] Dockerfile + Compose api（profile `app`；CI 不 build/up）
- [x] 100k Chunk opt-in 夹具（`PIVOT_REQUIRE_100K=1`；CI 默认 skip）
- [x] HTTP Embedding / bge-reranker 可注入适配器（CI Fake transport；非 live 供应商）
- [x] Dockerfile.web + Compose web（profile `app`；CI 不 build/up）
- [x] ingest `IndexPublisher` 写入注入 VectorStore（CI Fake client）
- [x] HTTP 上传后进程内自动 ingest（信封仍 `uploaded`；非 Celery）
- [x] Dockerfile.worker + Compose worker（profile `app`；CI 不 build/up）
- [x] 登录失败限流计数可注入 Redis CacheStore（缺省不锁定；不冻结 TBD-P0）
- [x] `PIVOT_STORAGE=postgres` 装配文档事实（Document/Version/Chunk/Task；sqlite 测试 URL）
- [x] `PIVOT_INGEST=celery` eager 任务可看见 PG version/task（CI memory broker）
- [x] Compose worker 为注入 Redis broker 的 Celery（只监听 parse；CI 不 build/up）
- [x] worker 装配共享 MinIO/PG ingest runner（CI sqlite + Fake MinIO；拒绝 memory 对象）
- [x] Compose api 注入共享 PG/MinIO（与 worker 同一套变量；不静默 memory）
- [x] worker 装配 Qdrant IndexPublisher（CI Fake client；Compose 注入 `PIVOT_VECTOR_STORE` / `PIVOT_QDRANT_*`）
- [x] Compose api 注入 `PIVOT_INGEST=celery`（队列/concurrency/broker `${:?}`；Dockerfile 装 worker[celery]；CI 不 build/up）
- [x] Compose api/worker 注入 Qdrant/Redis（`${}`，store 不静默 memory；example 占位 qdrant/redis；CI 不 build/up）
- [x] Compose api 注入登录限流阈值/窗口（`${:?}`，不写死次数；example fixture 占位；进程外缺省仍永不锁定；CI 不 build/up）
- [x] Wave 3 夹具收口评审（ND-W3-13；A1 完成 + 回归绿；tag `wave-3-integrated` ≠ P0 通过）
- [x] 导出任务 PostgreSQL 持久化（ND-W3-04；CI sqlite；公开 URL 仍 signer；无对象字节下载 HTTP）
- [x] PATCH 角色 / 重置密码 HTTP（ND-W3-07；`role` / `reset_password`；重置口令不进审计）
- [x] ingest 与检索共用注入 HTTP Embedding（ND-STG-01；CI Fake transport；Compose api/worker 注入 `PIVOT_EMBEDDING*`）
- [x] Deepseek-Flash Draft Writer（ND-STG-02；CI Fake transport；Compose 仅 api 注入 `PIVOT_LLM*`；缺省仍证据拼接）
- [x] MinerU 云解析器（ND-STG-03；CI Fake transport；Compose api/worker 注入 `PIVOT_PARSER*`；缺省仍启发式/stdlib）
- [x] dev-staging Compose overlay（ND-STG-04；nginx 默认 127.0.0.1:80；8GiB limits fixture；CI 不 up；ECS apply 待 Owner SSH/安全组/磁盘）
- [x] 会话/refresh 跨进程（ND-W3-05；hashed refresh 与 Conversation 走 SQLAlchemy；CI sqlite）
- [x] Run/EventLog 跨进程（ND-W3-14；CI sqlite；Claim/Citation 仍不入库）
- [x] SSE 长连接推送与 Next 去缓冲（ND-W3-08；POST 立即返回 received；逐帧推送；opt-in uvicorn；CI 默认 skip）
- [x] 真实解析库 extra（ND-W3-03；`worker[parse]` PyMuPDF/docx/pptx/xlsx；`PIVOT_PARSER=native`；CI 微型夹具；缺省仍启发式/stdlib）
- [x] opt-in Playwright 十页（ND-W3-10；`PIVOT_REQUIRE_PLAYWRIGHT=1`；CI 默认 skip；≠ GATE-P0-005）
- [x] 企业 Golden Set 脱敏摘录 / 评测入口（ND-P0-01；120 条；≠ GATE verified）
- [ ] Qdrant 100k 索引峰值、新 ECS 加密 OSS 备份恢复、live Embedding/rerank/MinerU 冒烟、staging ECS apply、业务部门复核 Golden Set
- [ ] 任一 `GATE-P0-*` verified

## 5. 未完成项与已知差距

- [x] Wave 0 基础已存在：`api/` 数据端口、`web/` 设计系统与 client；
- [x] Wave 1 领域服务已存在：auth/documents/retrieval/qa/runs/stream/exports/audit/parsing/chunking 与 `worker/`（Fake/stdlib）；
- [x] `spec/contracts/`、`spec/scenarios/`、`spec/acceptance/matrix.md` 已由 M00 建立；Golden Set v0.2-synthetic 已建（120 条合成）；企业集 v0.3 脱敏摘录已入库（120 条，非业务复核）；真实供应商 live 冒烟仍待；
- [x] `tests/` 已有 M00 契约 48、M03 数据 12、M08 基础 9、Wave 1 领域 97、M09 12、M10 8、M11 pipeline/ops/perf（合入后 45 passed / 2 skipped）；
- [x] 分组 CI（`.github/workflows/ci.yml` + `ops/run_grouped_tests.py`）已装配，不启动 Compose；
- [x] `docker-compose.yml` 依赖 fixture + opt-in `api` profile 已合入 main；CI **不得** `up`/`build`；本机未强制拉起；
- [x] FastAPI 健康装配：`GET /healthz`、`GET /readyz`（探测注入，失败闭环）；optional extra `http`；
- [x] FastAPI `/api/v1/auth/login|refresh|logout`（注入 AuthService 才挂载；HttpOnly refresh Cookie）；
- [x] FastAPI `GET/POST /api/v1/documents`（同时注入 DocumentService 与 AuthService 才挂载）；
- [x] FastAPI 文档详情/版本/重试/删除（`/documents/{id}` 及 `/versions|/retry|/delete`）；
- [x] FastAPI `GET /api/v1/search`（同时注入 RetrievalService 与 AuthService 才挂载）；
- [x] FastAPI `/api/v1/runs` 创建/详情/SSE 长连接/取消（同时注入 RunService、QaOrchestrator 与 AuthService 才挂载；POST 立即返回 received；uvicorn 长连接 opt-in skip）；
- [x] FastAPI `POST /api/v1/exports`、`GET /exports/{id}`、`GET /admin/audit-events`（分别与 AuthService 同时注入才挂载）；
- [x] FastAPI `POST /auth/change-password`、`GET/POST /admin/users`、`PATCH /admin/users/{id}`（status / role / reset_password）；
- [x] FastAPI `GET/POST /conversations`、`GET/DELETE /conversations/{id}`、`GET /conversations/{id}/messages`（与 AuthService 同时注入才挂载）；
- [x] FastAPI `GET /documents/{id}/preview`、`GET /documents/{id}/download`（与既有文档 router 同挂载；inline/attachment；不暴露 MinIO）；
- [x] Dockerfile + Compose api（profile `app`；默认 `docker compose up` 不起 api）；
- [x] Dockerfile.web + Compose web（profile `app`；默认 `docker compose up` 不起 web）；
- [x] Dockerfile.worker + Compose worker（profile `app`；默认 `docker compose up` 不起 worker；Celery + 注入 broker）；
- [x] `PIVOT_INGEST=celery` eager 任务适配（CI memory broker；缺省仍进程内 ingest）；
- [x] worker 进程装配共享 MinIO/PG ingest runner（CI sqlite + Fake MinIO；拒绝 memory 对象）；HTTP 缺省仍进程内 ingest；Compose api 已注入同一套 DATABASE_URL/MinIO 与 `PIVOT_INGEST=celery`；`PIVOT_VECTOR_STORE=qdrant` 时 worker 装配 IndexPublisher（CI Fake client）；
- [x] PostgreSQL 用户目录、文档事实与导出任务客户端（SQLAlchemy；默认 CI 用 sqlite；Compose Postgres 为 opt-in skip）；
- [x] MinIO 文档与导出对象（默认 CI 用内存 client；公开导出 URL 仍为 signer；Compose MinIO 为 opt-in skip）；hashed refresh、Conversation 与 Run/EventLog 可走 SQLAlchemy（CI sqlite）；Claim/Citation 仍不入库；
- [x] Qdrant 向量客户端（默认 CI 用内存 client；Compose Qdrant 为 opt-in skip）；dense 检索可消费 VectorStore；ingest `IndexPublisher` 可 `upsert`（CI Fake client）；HTTP 上传默认可进程内 ingest；`PIVOT_INGEST=celery` 为 eager；Compose api 注入 celery ingest（CI 不 up）；Compose worker 注入 broker 只听 parse，并装配共享 MinIO/PG runner 与 Qdrant IndexPublisher；Compose api/worker 注入同一套 Qdrant 变量（CI 不 up）；`PIVOT_EMBEDDING=http` / `PIVOT_RERANK=bge` 可注入（CI Fake HTTP，非 live 供应商）；ingest 与检索共用同一注入 HTTP embedder；stdlib BM25 可注入；`PIVOT_PARSER=mineru` 可注入云解析器（CI Fake HTTP；Compose api/worker 注入 `PIVOT_PARSER*`；缺省仍启发式/stdlib）；`PIVOT_PARSER=native` 可装配 `worker[parse]` 真实库（CI 微型夹具；未装 extra 失败闭环）；
- [x] Redis 缓存/队列客户端（默认 CI 用内存 client；Compose Redis 为 opt-in skip）；登录限流计数可注入 Redis CacheStore；Compose api 注入阈值/窗口（不写死次数；进程外缺省不锁定）；Compose Celery broker 为注入 fixture；Compose api/worker 注入 cache/queue/Redis endpoint（CI 不 up；Redis 不是业务事实源）；
- [ ] 真实 PG Alembic 冒烟因无 Docker/psycopg 为 skip；
- [ ] 所有 `TBD-P0` 均未冻结，禁止模块自行填默认值；
- [ ] P0 八项门槛均未验证；
- [x] Wave 0 三项变更申请已批准：`20260906-M00-contract-test-path.md`、`20260906-M03-ownership-clarification.md`、`20260906-M08-web-scaffold-ownership.md`。
- [x] Wave 1 观测包变更已批准：`20260906-M06-observability-package-init.md`。
- [x] Wave 1 `argon2-cffi` 已写入 pyproject：`20260906-M01-auth-dependencies.md`（2026-09-09 composition root 落实）。
- [ ] LangGraph 尚未安装到原环境/正式依赖或接入业务；02-C 仅在 `.pi/` 双隔离 venv 验证并提交 proposed 候选锁。旧 `20260906-M05-langgraph.md` 暂缓已被 ADR-009 取代，ND-AGENT-02 的预算/依赖 Contract 待签认/发布。`20260906-M07-worker-dependencies.md` 的 Celery extra 与解析库 extra 已落实。
- [x] Wave 3 FastAPI 健康端点已批准并合入：`20260907-M11-fastapi-health-assembly.md`。
- [x] Wave 3 认证 HTTP 挂载已批准并合入：`20260907-M11-api-v1-auth-mount.md`。
- [x] Wave 3 文档上传/列表 HTTP 挂载已批准并合入：`20260907-M11-api-v1-documents-mount.md`。
- [x] Wave 3 文档详情/版本/重试/删除 HTTP 已批准并合入：`20260907-M02-documents-lifecycle-http.md`。
- [x] Wave 3 搜索 HTTP 挂载已批准并合入：`20260907-M11-api-v1-search-mount.md`。
- [x] Wave 3 Run/SSE HTTP 挂载已批准并合入：`20260907-M11-api-v1-runs-sse-mount.md`。
- [x] Wave 3 导出/审计 HTTP 挂载已批准并合入：`20260908-M11-api-v1-export-audit-mount.md`。
- [x] Wave 3 改密/管理用户 HTTP 已批准并合入：`20260908-M01-auth-admin-users-http.md`。
- [x] Wave 3 会话 CRUD HTTP 已批准并合入：`20260908-M11-api-v1-conversations-mount.md`。
- [x] 主线开发流程已批准：`20260908-M00-mainline-development.md`（MODULE-SPEC-1.1）。历史 worktree 由 Owner 手动清理。
- [x] Wave 3 预览/下载 HTTP 已批准：`20260908-M02-documents-preview-download-http.md`。
- [x] Wave 3 composition root 已批准：`progress/changes/20260909-M11-composition-root.md`。
- [x] Wave 3 Next `/api/v1` 反代已批准：`progress/changes/20260909-M08-next-api-proxy.md`。
- [x] Wave 3 opt-in Playwright 登录已批准：`progress/changes/20260909-M11-playwright-login.md`。
- [x] Wave 3 PostgreSQL 用户目录客户端已批准：`progress/changes/20260909-M03-postgres-user-directory.md`。
- [x] Wave 3 MinIO 文档对象客户端已批准：`progress/changes/20260909-M03-minio-object-store.md`。
- [x] Wave 3 Qdrant 向量客户端已批准：`progress/changes/20260909-M03-qdrant-vector-store.md`。
- [x] Wave 3 Redis 缓存/队列客户端已批准：`progress/changes/20260909-M03-redis-cache-queue.md`。
- [x] Wave 3 Golden Set v0.1-synthetic 已批准：`progress/changes/20260909-M11-golden-set-synthetic.md`。
- [x] Wave 3 导出对象 MinIO 已批准：`progress/changes/20260909-M11-minio-export-objects.md`。
- [x] Wave 3 检索接 Qdrant 已批准：`progress/changes/20260909-M04-qdrant-retrieval.md`。
- [x] Wave 3 5 并发与进程内备份夹具已批准：`progress/changes/20260909-M11-capacity-backup-fixture.md`。
- [x] Wave 3 stdlib BM25 / 可注入 rerank 已批准：`progress/changes/20260909-M04-bm25-rerank.md`。
- [x] Wave 3 Dockerfile / Compose api 已批准：`progress/changes/20260909-M11-compose-api.md`。
- [x] Wave 3 100k Chunk opt-in 夹具已批准：`progress/changes/20260909-M11-chunk-capacity.md`。
- [x] Wave 3 HTTP Embedding / bge-reranker 适配器已批准：`progress/changes/20260909-M04-http-embedding-bge-rerank.md`。
- [x] Wave 3 Dockerfile.web / Compose web 已批准：`progress/changes/20260909-M11-compose-web.md`。
- [x] Wave 3 Golden Set v0.2-synthetic 已批准：`progress/changes/20260909-M11-golden-set-v02.md`。
- [x] Wave 3 ingest→Qdrant 已批准：`progress/changes/20260910-M07-ingest-qdrant.md`。
- [x] Wave 3 HTTP 上传自动 ingest 已批准：`progress/changes/20260910-M11-http-upload-ingest.md`。
- [x] Wave 3 Dockerfile.worker / Compose worker 已批准：`progress/changes/20260910-M11-compose-worker.md`。
- [x] Wave 3 Redis 登录限流已批准：`progress/changes/20260910-M01-redis-login-rate-limit.md`。
- [x] Wave 3 PostgreSQL 文档事实已批准：`progress/changes/20260910-M03-postgres-document-facts.md`。
- [x] Wave 3 Celery ingest 已批准：`progress/changes/20260910-M07-celery-ingest.md`。
- [x] Wave 3 Compose Celery worker 已批准：`progress/changes/20260910-M11-compose-celery-worker.md`。
- [x] Wave 3 worker 共享 MinIO/PG ingest 已批准：`progress/changes/20260910-M07-worker-minio-ingest.md`。
- [x] Wave 3 Compose api 共享 PG/MinIO 已批准：`progress/changes/20260910-M11-compose-api-shared-storage.md`。
- [x] Wave 3 worker Qdrant IndexPublisher 已批准：`progress/changes/20260910-M07-worker-qdrant-index.md`。
- [x] Wave 3 Compose api celery ingest 已批准：`progress/changes/20260910-M11-compose-api-celery-ingest.md`。
- [x] Wave 3 Compose api/worker Qdrant/Redis 已批准：`progress/changes/20260910-M11-compose-api-worker-qdrant-redis.md`。
- [x] Wave 3 Compose api 登录限流已批准：`progress/changes/20260910-M01-compose-login-rate.md`。
- [x] Wave 3 夹具收口评审已批准：`progress/changes/20260910-M11-wave3-closeout.md`。
- [x] Wave 3 导出任务 PostgreSQL 持久化已批准：`progress/changes/20260914-M06-postgres-export-tasks.md`。
- [x] Wave 3 PATCH 角色/重置密码 HTTP 已批准：`progress/changes/20260914-M01-admin-patch-role-reset.md`。
- [x] staging ingest/检索共用 HTTP Embedding 已批准：`progress/changes/20260914-M07-ingest-http-embedding.md`。
- [x] staging Deepseek-Flash Draft Writer 已批准：`progress/changes/20260914-M05-http-draft-writer.md`。
- [x] staging MinerU 云解析器已批准：`progress/changes/20260914-M07-mineru-cloud-parser.md`。
- [x] staging Compose overlay 已批准：`progress/changes/20260914-M11-compose-staging.md`。
- [x] Wave 3 会话/refresh 跨进程已批准：`progress/changes/20260914-M01-postgres-refresh-conversations.md`。
- [x] Wave 3 Run/EventLog 跨进程已批准：`progress/changes/20260914-M05-postgres-run-eventlog.md`。
- [x] Wave 3 SSE 长连接已批准：`progress/changes/20260914-M05-sse-long-connection.md`。
- [x] Wave 3 真实解析库 extra 已批准：`progress/changes/20260914-M07-native-parsers.md`。
- [x] Wave 3 opt-in Playwright 十页已批准：`progress/changes/20260914-M11-playwright-ten-pages.md`。
- [x] 企业 Golden Set 标注规范与空 schema 已批准：`progress/changes/20260914-M11-golden-set-enterprise-schema.md`。
- [x] 企业 Golden Set v0.3 脱敏摘录已批准：`progress/changes/20260914-M11-golden-set-enterprise-fill.md`。

## 6. 轮次日志

轮次日志已经拆出，见 [progress/history/progress-log.md](progress/history/progress-log.md)。本文件只维护现行状态。后续轮次记录直接写入轮次日志文件。

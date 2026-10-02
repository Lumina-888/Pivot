# ND-AGENT-02-C：Python 3.12 框架依赖验证与锁定申请

- **日期 / 状态**：2026-10-02 / proposed；ND-AGENT-02-C review，待消费者及 Owner 审核，不是依赖发布或业务实现放行。
- **提案版本**：AGENT-DEPENDENCIES-0.1-draft.1。
- **Accountable / 申请人**：M03 主线会话；M05 框架消费者、M11 验证/证据与后续 CI/镜像、M00 治理、M01 敏感状态/供应链审核。
- **来源**：[SPEC-1.1 §7/§9.1](../../SPEC.md)、[AGENT_SPEC §8.1/§10](../../spec/AGENT_SPEC.md)、[ADR-009](20261002-M00-langgraph-react-baseline.md)、[02-C 工单](../tickets/spec-1.1-remaining.md#nd-agent-02-c-框架依赖与锁定)。
- **原契约**：公开 contract-v0.1 不变；[02-A](20261002-M05-agent-internal-contract.md) / [02-B](20261002-M05-agent-budget-contract.md) 仍 proposed/review；此前没有 Python 锁文件、LangGraph/消息/供应商适配/checkpointer 依赖。
- **开场基线**：main `11e8a8c`；六处已有业务源码修改及用户未跟踪文件全部保留、不纳入本刀。

## 1. 范围与准入

本刀只使用仓库 `.pi/artifacts/nd-agent-02-c/` 内新建的两个 CPython 3.12 隔离 venv 验证公开包及合成 Fixture，提交候选锁、版本矩阵、可重跑探针和依赖申请。没有修改 `api/pyproject.toml`、worker 元数据、正式锁路径、CI/Dockerfile、业务源码、路由、迁移、公开 schema 或生产配置；原 `.venv` 64 个已捕获第三方版本未变，LangGraph 仍未安装其中。

技术探针的执行边界来自 02-C ready 范围：公开 import、消息序列化、工具 schema、MockTransport、真实但独立的 StateGraph/InMemorySaver 技术夹具。不是在 Pivot 中运行新 Agent，不调用真实供应商、PostgreSQL、Compose 或 ECS。有限步数、synthetic thread、Mock model、dummy key 均不是运行许可或生产默认。

**框架接口可用 ≠ FR-AGENT-001/004/006/009 verified。** 缺框架 fail-closed、真实 Planner 选择、累计预算、恢复授权及模型能力门禁仍是后续业务 Red；本刀 import Red 不冒充已实现 Agent 启动失败门禁。

## 2. Python 3.12 候选版本矩阵

候选来自本轮公开 PyPI 元数据和实际 wheel resolver，所有选择的 artifact 均非 yanked；不是对未来 latest 的浮动安装承诺。

| 包 / 拟议安装层 | 精确候选 | 上游 Python / 关键依赖约束 | 本轮证据 |
|---|---|---|---|
| langgraph / `agent` | 1.2.12 | >=3.10；core >=1.4.7,<2；checkpoint >=4.1,<5 | StateGraph、条件边、MessagesState、同步/异步执行可用 |
| langchain-core / `agent` | 1.6.6 | >=3.10,<4；Pydantic >=2.7.4,<3；httpx >=0.23,<1 | AI/Tool/HumanMessage、消息字典与 msgpack 往返 |
| langgraph-checkpoint / `agent` | 4.2.0 | >=3.10；core >=0.2.38；ormsgpack >=1.12 | InMemorySaver、JsonPlusSerializer、interrupt/Command 合成探针 |
| langchain-openai / `agent-openai`（可选候选） | 1.6.7 | >=3.10,<4；core >=1.6.6,<2；openai >=2.45,<4 | Chat Completions 的 Mock 工具 schema/ID/ToolMessage/用量往返 |
| langgraph-checkpoint-postgres / `agent-postgres`（后续持久化） | 3.1.2 | >=3.10；checkpoint >=4.1,<5；psycopg/pool >=3.2 | 同步 Saver import；无 DB setup/读写/重启证据 |
| psycopg[binary] / `agent-postgres` | 3.3.6 | >=3.10；binary 必须同为 3.3.6 | 公开 Saver 依赖导入可用，不证明 libpq/Linux/PG 运行 |
| psycopg-pool / `agent-postgres` | 3.3.3 | >=3.10 | pool import 可用；池生命周期/并发未验收 |
| openai / 可选适配的传递依赖 | 3.23.0 | 由候选 adapter 约束解析并精确锁定 | MockTransport；不是供应商工具能力确认 |
| Pydantic / httpx / FastAPI / Celery | 2.13.5 / 0.28.1 / 0.141.1 / 5.5.3 | 保留当前已有版本；不升级无关依赖 | 含新候选的既有分组回归通过 |

验证环境：Windows AMD64、Python 3.12.10、pip 25.0.1、pytest 9.1.1、ruff 0.16.6。没有对 Python 3.10/3.11/3.13 扩大本仓 `>=3.12,<3.13` 约束。

本轮将既有 API 的 test/lint/http/postgres/minio/qdrant/redis、worker celery/parse、公共契约测试及全部候选合并解析为 **111 个 wheel**；**62 个重叠既有包版本未变，49 个新增闭包项**。另外两个原环境包不在所选闭包中；这不是“64 个包全部进锁”。新闭包包括 SDK、LangSmith、prebuilt、原生序列化/哈希等库，不能把它们视为无成本、无安全审核的隐形依赖。

## 3. 关键实测语义与消费者约束

### 3.1 原生消息 / 工具 / 模型适配

- AIMessage.tool_calls 的 name/args/id 与 ToolMessage.tool_call_id 可经过消息字典和 JsonPlusSerializer 往返；用量与显式 consumed 字段保留。
- strict Pydantic 工具参数可拒绝空 query 和额外 scope；provider schema strict 不替代服务端白名单、严格参数、身份/scope、单调用与调用 ID 校验。
- **预格式化 `{"type":"function",...}` 字典会被 core 原样返回**：`bind_tools(strict=True)` 不自动补其 strict/additionalProperties。必须从严格 Pydantic/StructuredTool/裸 function schema 标准化后检查最终 wire schema；已格式化字典须自行携带并验明 strict。探针保留此负向 canary，不能仅检查 bind 参数就宣称安全。
- Mock 仅验证 Chat Completions 路径、禁并行参数、两次原生工具往返和总 token；没有证明主备 live 模型、流式用量、structured Finalizer、取消/超时、非法 JSON 或 retry 分类。
- langchain-openai 是可选评估适配，不选择实际供应商/模型，不替换既有 HttpDraftWriter；ND-AGENT-05-A 也可采用既有 httpx + core 的专用原生工具适配，须另行能力/兼容确认。

### 3.2 recursion_limit 不可作为累计硬额度

本轮首个错误假设是“首次 limit=3，None 恢复 limit=2 后累计 count=5”。实际 **3 → 7**。独立最小探针确认：新输入 limit=1/2/3 分别执行 1/2/3 个 tick；同 thread 的 `invoke(None, config)` 又执行 **3/4/5** 个 tick（limit+2），之后才 GraphRecursionError。

安装包 `langgraph/pregel/_loop.py` 的恢复初始化、input super-step 与 stop 计算解释此差异；不改第三方源码，也不把观察值当生产参数。相同 checkpoint 再 invoke 会得到新的技术窗口。

**02-B §4 的 `min(技术上限, 剩余 super-steps)` 映射单独不够。** M05/M11 签认前须明确每次实际调度/节点边界的独立累计计数和派发门禁，覆盖 None/Command、重放、同步/异步、分支/多节点 super-step；不得靠调小默认值或减 2 的补丁替代 BudgetGate。修订/发布预算 Contract 与业务 Red 属后续批准切片，本刀不关闭 DR-010、不授权运行。

### 3.3 Checkpoint 不是敏感字段过滤器

- InMemorySaver 的同对象重编译可读回消息/终态，另一 thread 无旧数据；这不是跨进程恢复，也不证明恢复授权。
- interrupt/Command 恢复会重新执行节点 interrupt 前的前缀；不得放置非幂等审计、计费或业务写入。合成 consumed=7 没有清零，但不是预算账本验收。
- JsonPlusSerializer 即使 `pickle_fallback=False` 也会保留 AIMessage.additional_kwargs 的合成 reasoning_content canary。必须先做 State/消息字段白名单，移除凭证、endpoint、供应商私有 reasoning、完整系统 Prompt，再序列化；框架不会自动脱敏。不开放 pickle fallback 或任意自定义模块反序列化。
- langchain-core 传递依赖 LangSmith；批准实现需显式关闭 tracing/无遥测凭证，禁止原始敏感消息被框架自动外发。受控探针已设置 `LANGCHAIN_TRACING_V2=false`、`LANGSMITH_TRACING=false`，模型仅用 MockTransport。
- PostgreSQL Saver 上游 from_conn_string 使用 autocommit=True、prepare_threshold=0、dict_row；setup() 创建/升级自身 checkpoint 表。不得在未批准的业务请求/启动中偷偷 setup 或当 Alembic 事实迁移；权限、表隔离、迁移、加密/保留及回滚经 DR-011/04-A/C 冻结。

## 4. 候选锁与可重建性

版本化技术材料（Accountable M03；M11 证据路径）：

- [candidate-win-py312.lock.txt](../../evidence/agent-m03/nd-agent-02-c/candidate-win-py312.lock.txt)：全验证闭包，每包 `==` + 本次 Windows/通用 wheel 的 SHA-256；**不是 API/生产锁**。
- [candidate-manifest.json](../../evidence/agent-m03/nd-agent-02-c/candidate-manifest.json)：111 项版本/依赖元数据/轮子名/哈希、29 条 solver roots、平台与 pip、现有项目输入摘要、pending 审核标识。文本摘要按 UTF-8/LF 规范化，避免 Git autocrlf 造成伪差异；wheel 哈希始终是原始字节摘要。
- [test_dependency_probe.py](../../evidence/agent-m03/nd-agent-02-c/test_dependency_probe.py)：11 项公开接口/负向 canary/锁一致性探针，显式运行，不混入默认业务回归。
- [本轮验证记录](../../evidence/agent-m03/nd-agent-02-c.md)：Red、安装/离线重建、版本、回归、限制与复跑命令。

首次 dry-run 使用官方 PyPI、only-binary 与 64 个当前版本 constraints，生成 report；下载全部 wheel 时 require-hashes；随后两个**全新** venv 均从本地 wheelhouse 用 `--no-index --require-hashes --only-binary=:all:` 重建，pip check 与 11 项探针通过。错误 SHA-256 Fixture 的 dry-run 明确退出 1、拒绝 wheel，没有安装修改。

不提交 `.pi/` venv、wheelhouse、原始完整 registry/report 或含路径的安装日志。候选 manifest/锁已足够按相同平台下载并重跑，不承诺注册表永久可用；批准发布需受控 artifact mirror/保留策略。

**禁止把 Windows 哈希锁复制给 Linux。** python:3.12.10-slim-bookworm 与 ubuntu CI 未实际验证。跨平台 binary/marker 及镜像原生库需在真实 Linux x86_64 环境独立解析、下载/安装/回归；不能用宿主 Windows 的 pip `--platform` 输出冒充目标 marker 或容器验证。

## 5. 批准后的发布 / CI / Docker 方案（未执行）

1. M03 串行维护 optional extras：`agent` 仅框架/core/checkpoint 的以上精确候选；`agent-openai` 为批准的可选适配；`agent-postgres` 为批准持久化包/匹配 psycopg binary/pool。默认依赖不强装供应商 SDK，解析 worker 不因 API Agent 增加框架。
2. 正式第三方锁拟存 `api/locks/`，按 `ci-py312-linux-x86_64`、`runtime-agent-py312-linux-x86_64`、`dev-agent-py312-win-amd64` 分层；Worker 在自己的锁中只保留需要的 celery/parse 闭包。此路径/文件尚未发布；直接版本与共享传递依赖在角色锁间一致，不升级无关版本。
3. M11 在 CI 明确安装经批准的测试/框架锁，新增这组依赖探针，并保持现有分组/不启动 Compose。CI 当前 setup-python 3.12 浮动 patch、pip 升级与 editable 自由解析，正式锁执行须同时固定工具链并改为 require-hashes，不宣称当前 CI 已消费候选锁。
4. API 镜像只安装批准运行层锁；Agent 无恢复阶段不提前启用 PostgresSaver。worker 镜像不装 Agent；保留无关角色文件。冻结 Python image digest/OS 库与 build-tools（setuptools/wheel）单独锁，第三方包 hashes 安装后，本项目用受控构建产物/哈希及 `--no-deps` 安装，不再触发隐式依赖解析。开发 editable 也 `--no-deps`，构建使用已锁的 build tools/无自由 build isolation 下载。当前候选不是此完整构建发布锁。
5. dependency_set_id + manifest 摘要、graph/State/Prompt/tool/model 版本按 Run 固定并供 checkpoint 恢复校验；持久字段与迁移由 04-A/E 承接，不在本刀加列。升级后不能给旧 Run 静默换图/框架或反序列化不兼容 State。
6. 升级先对候选锁作依赖/许可证/漏洞审核，验证 Linux、公开协议、negative probes、旧回归及批准恢复夹具；审批后才发布。回滚固定上一依赖锁/镜像；若已升级 checkpoint schema，禁止只降 wheel，必须经 DR-011 批准迁移/备份恢复协议。没有可批准回滚的兼容证据则暂停/排空旧 Run，不重置预算或 fallback。

## 6. 验证、计划 Red 与边界

本轮技术验证：导入 Red **1 failed** → 隔离依赖导入 passed；最终 **11 probes passed**，两个 venv 均成功 hashes/offline 重建；候选环境既有分组 **661 passed / 19 skipped**，ruff/compileall passed。详情与首次探针误假设、文本摘要换行修正见证据。

后续未实施的业务 Red 保留：

| 测试 ID | 负责切片 / 验收边界 |
|---|---|
| test_FR_AGENT_009_missing_graph_dependency_fails_closed | 02-G/装配：Agent 明确请求缺图时停止，模型/旧线性派发均为 0 |
| test_FR_AGENT_009_tool_capability_required | 02-A/G、05-A/B：主备能力必须单独确认，无工具协议拒绝 |
| test_FR_AGENT_006_checkpoint_version_compatible | 04-A/C：生产版本固定、不兼容拒绝/批准迁移、PG setup 与真实往返 |
| test_FR_AGENT_004_budget_survives_resume | 02-F/G、04-C/E：节点/真实 super-step 累计门禁不被 limit+2/重新 invoke 绕过 |
| test_FR_AGENT_003_private_reasoning_never_checkpointed | 02-E、04-C：服务端消息白名单，序列化前截断敏感字段，外发/公开轨迹不得泄漏 |

不把技术测试名下的 FR-AGENT 关联当需求通过；未验证安全审计、许可证/CVE 全量审核、Linux/镜像、PG 故障/租约、真实模型、端到端取消或任何 GATE。无预算默认、新接口、状态或错误码变化。

## 7. 待签认与审核结果

| 审核方 | 必须签认 / 补齐 | 结果 |
|---|---|---|
| M03 | 精确版本/角色锁、构建工具、跨平台 artifact、版本固定及回滚范围 | pending；作者不等于批准 |
| M05 | core 消息/strict 工具适配、recursion_limit 恢复差异；02-B 独立硬门禁 | pending；未发布预算修订 |
| M11 | Linux 3.12 真实安装/分组/镜像验证，CI 锁执行与角色隔离 | pending；无 Linux/镜像证据 |
| M01 | 新增 SDK/遥测/序列化白名单、依赖许可证/漏洞与 artifact 来源审核 | pending；无全量安全结论 |
| M00 | 02-A/B/C 版本兼容、发布门禁、事实/公开契约无隐式变化 | pending；不加入 contract-v0.1 manifest |
| Owner / 运维 | 可选适配安装范围、受控 artifact 与变更/回滚授权 | pending；不选择供应商/模型或授权生产安装 |

**ADR**：落实 ADR-009 的依赖前置，不新增状态/权限/模型配置裁决；DR-001/007/010/011 不关闭。若审批改变实际模型/外发/恢复策略，须追加对应 ADR，不由依赖提案隐式决定。

## 8. 下一步

02-C 移至 review，不标 done；02-A/B/C 均待签认。优先处理上述六项审核、Linux 锁验证及预算映射修订确认，全部 DoR 满足后才安排 02-D/E/F/G/H。若要先推进不依赖审批的另一文档切片，可选择 ND-AGENT-03-A 恢复公开 Contract 提案（只 proposed），不能发布路由。父票/DR-010/011、TBD-P0、所有 GATE 继续 blocked/unverified。

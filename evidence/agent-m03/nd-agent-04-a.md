# ND-AGENT-04-A 持久化 Contract 提案证据

## 1. 范围与环境

2026-10-03，main修改前基线`d613318`，开场`git status --short --branch` clean。M03 Accountable；M00 proposed schema/根级契约测试/工单与README，M05消费进度，M11回归/证据，根PROGRESS/HANDOFF同步。没有子代理、worktree或用户文件改动。

- CPython3.12.10，解释器`/home/lumina888/Projects/Pivot/.venv/bin/python`；pytest9.1.1、jsonschema4.26.0、ruff0.16.6。
- 本机Linux现有venv；不安装LangGraph/PG Saver/新格式校验依赖，不改pyproject/正式锁/CI/镜像/Compose/迁移。
- [AGENT-PERSISTENCE-0.1-draft.1](../../progress/changes/20261003-M03-agent-persistence-contract.md) proposed；[独立schema](../../spec/contracts/proposals/agent-persistence.schema.json)只覆盖内部元数据，不是AgentState/DDL/恢复API。04-A review，7项消费者/Owner签认pending，DR-011未关闭。

## 2. Red 与 Green

测试边界来自04-A票的Contract调研/提案范围；[测试文件](../../tests/contract/test_contract_agent_persistence_proposal.py)明确是shape checks，不冒用运行时fencing/恢复测试名宣称实现通过。

```bash
cd /home/lumina888/Projects/Pivot
.venv/bin/python -B -m pytest tests/contract/test_contract_agent_persistence_proposal.py -q -p no:cacheprovider
```

1. 缺schema：LeaseToken正向1 error，错误明确`ND-AGENT-04-A proposed schema is missing (Red)`；新增最小LeaseToken schema后1 passed。
2. 增加CheckpointBinding/ResultCommitReceipt/OutboxRecord/ProviderAttempt/GovernancePolicy正向：缺组件5 failed/1 passed；新增5组件后6 passed。
3. 增加必填/类型/白名单/版本/日期/枚举/用量/策略负向：第一轮命令30秒窗口超时，未作为完整结果。单独`-k timestamp --tb=short`复现2 failed/3 passed：无可选RFC3339 format checker时，jsonschema忽略date-time，接受2月30日/13月。
4. 不安装依赖；测试端显式注册stdlib datetime日历checker，结合schema UTC Z/T正则；缓存组件validator避免每项重复check_schema。修复LSP指出的utcoffset可空访问，ruff format整理新测试文件。
5. 最终上述完整命令：**173 passed in 2.99s**。覆盖六组件正向、每字段缺失、敏感额外字段、token/seq正整数、opaque ID/固定版本、非法UTC/日期、终态/原事件名、unknown不得假零/整数微币、治理期限正整数和未发布边界。

shape能证明字段类型/白名单，不能证明签认存在、真正加密State无reasoning、租约排他、版本匹配、跨对象引用、事务/事件唯一或日历checker已装到生产。实际消费者必须启用等价严格验证，不只读正则。

## 3. 完整 Python 分组回归

```bash
.venv/bin/python -B ops/run_grouped_tests.py --skip-web
```

| 分组 | 结果 |
|---|---|
| M01 auth/security | 37 passed |
| M02 documents | 28 passed |
| M04 retrieval/security | 31 passed |
| M05 QA/Run/SSE | 79 passed |
| M06 exports/audit/security | 26 passed |
| M07 worker | 79 passed |
| M00/M03 contract-db（含03-A/04-A提案） | 331 passed |
| M11 pipeline | 271 passed / 1 failed / 18 skipped |
| M11 security ops | 2 passed |
| M11 performance | 11 passed / 1 skipped |
| 合计 | **895 passed / 1 failed / 19 skipped** |

harness exit1，失败组M11-pipeline。唯一失败为已有`test_NFR_OBS_compose_staging_env_is_gitignored`：断言仓库根`.env`不存在，而本机配置文件存在（已在03-A证据登记）。未读取/删除该用户配置、未改无关测试、未跳过失败修绿。不能宣称全量绿或为文档提交打完成tag。

pipeline有两项Starlette/httpx/anyio弃用warning，未在本刀升级依赖。不同于上一轮724/1/17，本次新增173 shape，但pipeline由273/16skip变为271/18skip；本次未显式启用opt-in浏览器/SSE-live，不将环境选择造成的跳过当新增功能失败或验收。受控真实PG/checkpoint/多进程/供应商/备份没有运行。

另独立重跑既有公共契约，排除stream与两份proposed测试（这不是对全量失败的跳过修绿）：

```bash
.venv/bin/python -B -m pytest tests/contract --ignore=tests/contract/stream --ignore=tests/contract/test_contract_agent_resume_proposal.py --ignore=tests/contract/test_contract_agent_persistence_proposal.py -q -p no:cacheprovider
```

结果**48 passed in 1.59s**，只证明已发布contract-v0.1回归。

## 4. 静态与主动诊断

```bash
.venv/bin/ruff format --config api/pyproject.toml tests/contract/test_contract_agent_persistence_proposal.py
.venv/bin/ruff check --config api/pyproject.toml tests/contract/test_contract_agent_persistence_proposal.py
.venv/bin/python -m compileall -q tests/contract/test_contract_agent_persistence_proposal.py
```

ruff format1 file reformatted，后两命令exit0。harness自己的ruff（api/src、worker/src、pipeline/ops/perf）及compileall亦exit0。没有以格式化修改既有业务文件。

主动LSP检查新Python测试/JSON/提案共3文件：JSON与提案2 clean；Python2 findings（pytest missing import、jsonschema missing source），不是整体clean。`effective_config`确认cwd为home根，没有项目配置；项目venv实际import pytest/jsonschema成功且打印路径在`.venv/lib/python3.12/site-packages`，173运行通过。解释器错配作为工具限制保留，不改用户全局LSP配置或屏蔽告警。其他Markdown偶有LSP unavailable提示，不将其当完整诊断通过。

另用Node只读检查本刀13份Markdown/169个本地链接：0 missing；29票执行表0 ready/5 review/24 blocked、7项pending签认与结构化schema proposed/无default一致。`git diff --check` exit0，`git check-ignore .env`确认用户本机文件gitignored且不进入提交；未读取其内容。提交前另执行staged diff检查，提交范围仅本刀15个文档/schema/测试文件。

## 5. 治理与剩余风险

- 新设计明确原Saver put/put_writes也须受PG租约/fencing保护；仅节点入口检查不能阻止旧进程写checkpoint。适配器能力仍待锁版本真实PG验证，若不可实现则04-C blocked并重新提案，不降级保证。
- 事实提交与安全outbox同事务，网络发送至少一次/seq重放；ProviderCall可能重复计费，unknown保守预扣、稳定action/新attempt及晚到只对账，不能宣称exactly-once。
- 策略加载还需跨字段时序/保留/密钥关系与真实审批验证；schema数值仅unit_fake_only，不是TBD-P0生产默认。
- 7项签认全pending；当前0 ready/5 review/24 blocked。02-A/B/C/03-A/04-A需签认，02-C目标平台原生锁与批准PG环境仍缺；04-B~F/全部Agent父票仍blocked。
- 未发布公开Contract、业务错误/恢复接口或迁移，不改SPEC/状态机/权限/删除/引用语义，DR-010/011/TBD-P0/所有GATE不关闭。

下一步先消费者/Owner签认和目标平台锁/PG环境准备，再重新核对DoR；不能因形状、旧SQLite/QA或文档完成就推进Agent业务实现。

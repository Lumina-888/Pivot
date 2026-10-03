# ND-AGENT-03-A 恢复 Contract 提案证据

## 1. 范围与基线

- 日期2026-10-03；Linux x86_64 / Arch（kernel 7.2.5-3-omarchy、glibc2.44），仓库 `/home/lumina888/Projects/Pivot`、main、开场HEAD `20e8f15`且tracked/untracked工作区clean。
- M00 Accountable：[AGENT-RESUME-0.1-draft.1](../../progress/changes/20261003-M00-agent-resume-contract.md)、独立 [proposed schema](../../spec/contracts/proposals/agent-resume.schema.json)/README、根级契约测试、工单与入口；M05消费者进度；M11本证据/回归与进度。
- Python3.12.10；pytest9.1.1；jsonschema4.26.0；ruff0.16.6；PyYAML6.0.3；使用仓库已有`.venv`，不安装/升级依赖，不调用外部供应商，不拉起/重配Docker。
- 公开OpenAPI/SSE/Worker/业务错误枚举、SPEC、业务源码、Web、迁移、CI/镜像与生产默认均不变。

## 2. Red → Contract → Green

测试入口：[test_contract_agent_resume_proposal.py](../../tests/contract/test_contract_agent_resume_proposal.py)。命令均从仓库根执行：

```bash
.venv/bin/python -B -m pytest tests/contract/test_contract_agent_resume_proposal.py -q -p no:cacheprovider --tb=short
```

| 阶段 | 观察结果 | 含义 |
|---|---|---|
| Red：请求草案文件尚不存在 | 1 error，明确 `ND-AGENT-03-A proposed schema is missing (Red)` | 先有需求形状检查，不是业务Red |
| Green：仅定义请求组件 | 1 passed | 严格字符串请求可校验 |
| Red：增加回执/等待视图/错误测试 | 12 failed/1 passed，缺ResumeAccepted/Clarification/ResumeFailure引用 | 覆盖新增草案组件缺失，未失败于供应商/基础设施 |
| Green：补齐草案组件 | 13 passed | 合法shape/10组错误配对通过 |
| 完整严格性/兼容边界检查 | 62 passed | 21非法字段类型/空白、3缺字段、10伪造上下文字段、4错误回执状态、4私有等待字段、5错误配对、1敏感details、1未发布检查，外加13正向 |

schema默认根为ResumeRequest；其他组件以整个文档为解析根替换根 `$ref`。错误测试校验 `(http_status, body)`，不向线上body增加http_status字段。proposal-only测试有显式docstring/名称；没有把字段白名单测试冒充owner鉴权或幂等运行时验收。

提案登记12组待实施运行时Red，覆盖owner/停用/不可见、同键异参、同/不同键并发、终态后的回执重放、撤权、累计预算、资源/版本重检、取消/超时、非法JSON脱敏、Web与崩溃持久化。这些未运行，不能标为passed。

## 3. 回归与静态

### 分组Python回归（exit 1，如实保留）

```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python ops/run_grouped_tests.py --skip-web
```

| 组 | 结果 |
|---|---|
| M01-auth | 37 passed |
| M02-documents | 28 passed |
| M04-retrieval | 31 passed |
| M05-qa-stream | 79 passed |
| M06-export-audit | 26 passed |
| M07-worker | 79 passed |
| M00-M03-contract-db | 158 passed（原96+新62） |
| M11-pipeline | 273 passed / **1 failed** / 16 skipped |
| M11-security-ops | 2 passed |
| M11-performance-plan | 11 passed / 1 skipped |
| 总计 | **724 passed / 1 failed / 17 skipped**；harness exit1 |
| harness ruff / compileall | passed |

唯一失败：`tests/integration/pipeline/test_NFR_OBS_compose_staging.py::test_NFR_OBS_compose_staging_env_is_gitignored`，L246 `assert not (_ROOT / ".env").exists()`。本地根`.env`存在且 `git check-ignore .env` 返回 `.env`；它不在本刀tracked diff。未读取/输出配置内容，未删除/移动用户文件，未为修绿修改/跳过旧测试。该环境断言与合法本地ignored配置的兼容性需单独跟进；本轮**不宣称全量绿或安全扫描完成**。

pipeline有FastAPI/Starlette针对httpx、anyio BlockingPortal的既有弃用警告；不借本刀升级依赖。17项skip来自既有opt-in/环境条件，本轮不主动skip失败用例。

### 定向复核与检查命令

```bash
.venv/bin/python -B -m pytest tests/contract --ignore=tests/contract/stream -q -p no:cacheprovider
PYTHONPATH=api/src:worker/src .venv/bin/python -B -m pytest tests/unit/qa tests/unit/runs tests/contract/stream -q -p no:cacheprovider
.venv/bin/ruff check --config api/pyproject.toml tests/contract/test_contract_agent_resume_proposal.py
.venv/bin/ruff format --config api/pyproject.toml --check tests/contract/test_contract_agent_resume_proposal.py
git diff --check
```

定向复核：公共契约 **110 passed（旧48+新62）**、QA/Run/SSE **79 passed**；新测试ruff check与format --check通过；`git diff --check`通过。格式化仅新测试与JSON草案，无无关文件重排。Node文件系统核对变更12份Markdown的135个本地文档链接均存在，JSON可解析；执行索引29票/1 ready/4 review/24 blocked一致。该检查只核对链接目标文件，未验证Markdown锚点或消费者签认。

### 主动LSP与解释器限制

主动 `lens_diagnostics(source=lsp, scope=paths)` 初期报告测试L6 `pytest`缺失、L5 `jsonschema` source缺失。effective_config显示cwd为home而非Pivot解释器；实际 `.venv/bin/python -B -c 'import sys, pytest, jsonschema; print(sys.executable); print(pytest.__file__); print(jsonschema.__file__)'` 正常，模块均位于Pivot/.venv/lib/python3.12/site-packages，且62项schema测试确实执行。两项标记为解释器选择false-positive，不写源码ignore、不更改用户LSP/项目依赖，不声称Pyright完成完整类型证明。

Markdown初期分析unavailable；随后主动探测6文件，5 clean/1拟议证据链接尚不存在告警（本证据创建前），2项Python误报按disposition隐藏。最终主动探测14文件：13 clean/1 Marksman仍报告本证据创建前的非存在链接；实际本地135链接检查通过，该条标记为stale false-positive。两项Python导入告警按disposition隐藏；不将隐藏告警或早期unavailable声称为完整类型/文档lint证明。收尾延迟pyright runner另报 `failed (unknown)`，未提供可归因的类型检查结果；不宣称完整pyright通过，已运行测试/ruff结果不受此声明替代。

## 4. 结果、待签与下一步

- 03-A **review**，AGENT-RESUME-0.1-draft.1 **proposed**，7组签认均pending，未发布/非done。受理/重放/错误策略属于待审设计，不是业务事实。
- 当前29票：1 ready（04-A文档前置）、4 review（02-A/B/C/03-A）、24 blocked；02~05父票和所有业务实现仍blocked。
- 优先补02-A/B/C/03-A消费者/Owner签认与02-C目标平台锁验证；独立下一前置04-A proposed。DR-010/011、输入/等待/保留期TBD-P0及全部GATE不关闭。
- 未运行Web/typecheck/lint/Playwright、新真实StateGraph、HTTP resume、PG/checkpoint/多进程、供应商live、目标平台镜像/锁、CVE/许可证全量或新GATE验证。既有memory/local开发服务不作为真实Agent就绪证明。
- 无推送、发布或完成tag；按MODULE-SPEC默认只提交本刀文件到main，保留本地ignored配置与所有无关变更。

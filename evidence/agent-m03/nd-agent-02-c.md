# ND-AGENT-02-C Python 3.12 依赖验证证据

- **日期 / 状态**：2026-10-02；技术验证完成，依赖申请 proposed、工单 review；不是正式依赖发布、业务 Agent 或 GATE 验收。
- **申请**：[AGENT-DEPENDENCIES-0.1-draft.1](../../progress/changes/20261002-M03-agent-dependencies-lock.md)。
- **基线 / 责任**：main `11e8a8c`；M03 依赖 Accountable，M11 验证/证据，M05 消费约束，M00 治理同步。开场六处业务源码修改及全部已有用户未跟踪文件保留、不纳入提交；业务回归基于含这些修改的工作区，不单独验收它们。
- **环境**：CPython 3.12.10 Windows AMD64；pip 25.0.1 / pytest 9.1.1 / ruff 0.16.6 / Pydantic 2.13.5 / httpx 0.28.1 / FastAPI 0.141.1。PowerShell 5.1。没有真实密钥、企业正文或供应商请求。

## 1. 候选材料与矩阵

[Windows 精确哈希锁](nd-agent-02-c/candidate-win-py312.lock.txt)、[候选 manifest](nd-agent-02-c/candidate-manifest.json)、[公开接口探针](nd-agent-02-c/test_dependency_probe.py)。全部 candidate/pending，不是正式 `api/locks/` 文件。

| 根包 | 版本 | 本轮验证 |
|---|---|---|
| langgraph | 1.2.12 | StateGraph / MessagesState / 条件边 / 同步异步 / 技术步数 |
| langchain-core | 1.6.6 | AIMessage/tool_calls、ToolMessage、严格工具参数、序列化 |
| langchain-openai（可选候选） | 1.6.7 | 仅 Mock Chat Completions 原生工具/ID/用量 |
| langgraph-checkpoint | 4.2.0 | JsonPlusSerializer / InMemorySaver / interrupt / Command |
| langgraph-checkpoint-postgres | 3.1.2 | 同步 Saver import；不连接 PG |
| psycopg[binary] / psycopg-pool | 3.3.6 / 3.3.3 | 导入兼容；真实池/连接/恢复待后续 |

公开元数据查询使用官方 `https://pypi.org/pypi/<package>/json`，解析/下载仅官方 PyPI simple。首次解析含 29 个 roots、64 个旧版本 constraints，得到 111 个非 yanked wheel；62 个重叠既有版本保持原值，49 个新闭包项。全套验证同时包含 API test/lint/http/存储 extras、Worker celery/parse、公共契约测试；不是生产最小闭包。实际 root/完整依赖/平台/轮子哈希已在 manifest 记录。

## 2. Red → 安装 → 语义验证 → Regression

以下脚本/原始输出位于仓库 `.pi/artifacts/nd-agent-02-c/`；TEMP/TMP、wheelhouse、venv、日志与 pytest basetemp 均显式设在该目录，不写 C 盘。辅助脚本只生成技术材料、调用既有分组，不实现业务逻辑。

| 阶段 / 完整命令要点 | 结果 / 原始输出 |
|---|---|
| `.venv/Scripts/python -B -m pytest evidence/agent-m03/nd-agent-02-c/test_dependency_probe.py -q -p no:cacheprovider --basetemp=.pi/artifacts/nd-agent-02-c/pytest-red`（当时仅导入探针） | **1 failed**：ModuleNotFoundError langchain_core；`red.log`。不是 Pivot Agent 启动门禁测试 |
| `.venv/Scripts/python -B .pi/artifacts/nd-agent-02-c/inspect_registry.py` / `build_inputs.py` | 官方元数据、旧环境版本与 29 roots；本地 registry JSON / baseline constraints |
| `.venv/Scripts/python -B -m venv .pi/artifacts/nd-agent-02-c/verify-venv` | 新隔离环境；不污染原 `.venv` |
| `verify-venv/Scripts/python -B -m pip --isolated --disable-pip-version-check --no-cache-dir install --dry-run --only-binary=:all: --index-url https://pypi.org/simple -r .pi/artifacts/nd-agent-02-c/roots.txt -c .pi/artifacts/nd-agent-02-c/baseline-constraints.txt --report .pi/artifacts/nd-agent-02-c/resolve-report.json` | 解析成功，111 个 wheel；`resolve.log` |
| `.venv/Scripts/python -B .pi/artifacts/nd-agent-02-c/build_lock.py` | 生成候选锁/manifest；每项 == 与 wheel SHA-256；非发布 |
| `verify-venv/Scripts/python -B -m pip --isolated --disable-pip-version-check --no-cache-dir download --only-binary=:all: --require-hashes --index-url https://pypi.org/simple -r evidence/agent-m03/nd-agent-02-c/candidate-win-py312.lock.txt -d .pi/artifacts/nd-agent-02-c/wheelhouse` | hashes 下载成功；`download.log` |
| `verify-venv/Scripts/python -B -m pip --isolated --disable-pip-version-check --no-cache-dir install --no-index --find-links=.pi/artifacts/nd-agent-02-c/wheelhouse --only-binary=:all: --require-hashes -r evidence/agent-m03/nd-agent-02-c/candidate-win-py312.lock.txt` | 离线安装成功；`install.log`；pip check 无冲突 |
| `verify-venv/Scripts/python -B .pi/artifacts/nd-agent-02-c/probe_findings.py` | 独立最小语义探针确认恢复 limit+2 与字典 passthrough，见 §3 |
| `verify-venv/Scripts/python -B .pi/artifacts/nd-agent-02-c/run_checks.py` | 重用 ops/run_grouped_tests.py 的 10 组 GROUPS；最终技术探针 **11 passed**，既有 **661 passed / 19 skipped**，ruff/compileall passed；`checks-20261002-164852/`（首轮 `checks-20261002-161628/` 保留摘要错误记录） |
| `.venv/Scripts/python -B -m venv .pi/artifacts/nd-agent-02-c/rebuild-venv` 后，用同锁同 wheelhouse 执行上面的 offline hashes install | 第二个全新 venv 离线重建成功，`rebuild.log`；pip check 无冲突 |
| `rebuild-venv/Scripts/python -B -m pytest evidence/agent-m03/nd-agent-02-c/test_dependency_probe.py -q -p no:cacheprovider --basetemp=.pi/artifacts/nd-agent-02-c/pytest-rebuilt` | **11 passed**（版本/锁/输入一致性含在内） |
| `rebuild-venv/Scripts/python -B -m pip --isolated --disable-pip-version-check --no-cache-dir install --dry-run --ignore-installed --no-index --find-links=.pi/artifacts/nd-agent-02-c/wheelhouse --only-binary=:all: --require-hashes -r .pi/artifacts/nd-agent-02-c/bad-hash-fixture.txt` | 期望 **exit 1**；xxhash 零哈希与真实 wheel 不符，明确拒绝；`bad-hash.log`，没有实际安装 |

表中 `verify-venv/Scripts/python` / `rebuild-venv/Scripts/python` 均指 `.pi/artifacts/nd-agent-02-c/` 下的对应路径，不是 PATH 中的解释器。

既有分组明细：auth 37、documents 28、retrieval 31、QA/Run/SSE 79、export/audit 26、worker 79、公共契约/DB 96、pipeline 272 passed/18 skipped、ops 2、perf 11 passed/1 skipped，总计 **661 passed / 19 skipped**。pipeline 保留一项 Starlette BlockingPortal alias 弃用警告。没有 Web/Compose/Playwright/SSE-live/100k/真实供应商运行。

首轮扩展探针 **2 failed / 7 passed**，原因是未验证的技术假设，而非业务源码缺陷；不修第三方包、不降低安全门槛。最小探针确认后保留负向 canary 与精确版本行为断言，改用正规化裸 function schema 验证 wire strict。随后 **10 passed / 1 failed** 是生成器对 LF 文本计算摘要却写出 CRLF 的辅助错误；修为 UTF-8/LF 规范化文本摘要（wheel 哈希仍为原始 bytes），兼容 Git autocrlf，两个环境最终均 **11 passed**。初次 import排序提示用 ruff 修正。

## 3. 实测发现与未通过边界

1. **技术 recursion 不是 Run 硬预算**：新输入 limit=1/2/3 → ticks=1/2/3；同 thread 的 None 恢复 → 新 ticks=3/4/5。limit=3 首次 count=3 后以 limit=2 恢复，最终 count=7。安装包 `_loop.py` 恢复初始化/stop 与输入步数解释结果。02-B 映射须经 M05/M11 补充独立调度/节点累计 gate，不能只用 min(remaining, recursion_limit)，不关闭 DR-010。
2. **strict 参数不硬化预格式化字典**：core `convert_to_openai_tool` 对 type=function 原样返回，不补 strict/additionalProperties；裸 function schema/严格 Pydantic 能正规化，最终 wire schema 通过 Mock 检查。需服务端继续拒绝额外参数、未知工具、多调用和 ID 错配。
3. **serde 不脱敏**：合成 reasoning_content canary 被完整保留。必须序列化前字段白名单；pickle_fallback=False 不等于安全过滤。没有真实秘密进入探针。
4. **interrupt 前缀重跑**：同 InMemorySaver 重编译/Command 恢复两次进入节点前缀，consumed 合成值保留；不是跨进程/PG 重启、幂等账本、租约或授权验证。
5. **PG 只到 import**：真实 PostgreSQL setup/表迁移/写读/池/重启与 OS libpq 未执行；同步/异步公开 Saver API 的设计须在 04-A/C 验证。无 DR-011 关闭证据。
6. **新增闭包需安全审核**：core 含 LangSmith，框架含 prebuilt；探针关闭 tracing、仅注入 MockTransport（http_socket_options=()）。不启用外部自动遥测/任意工具，不宣称全量许可证/CVE 已审核。
7. **Linux 没有验证**：Windows 哈希不能用于 slim-bookworm/ubuntu；无 Docker build/up/镜像与 Linux 安装证据。Python >=3.10 上游支持标记不是本仓其他 Python 版本验收。

静态/材料检查：`.venv/Scripts/python -B .pi/artifacts/nd-agent-02-c/check_delivery.py` → **12 Markdown / 92 本地链接 / 29 票（2 ready、3 review、24 blocked）/ 111 个实际 wheel SHA-256 / 62 个重叠旧版本检查 passed**；candidate Python 的 ruff 检查业务/受影响测试与技术 probe，以及全部 artifact 辅助脚本 passed；compileall 与 `git diff --check` passed。辅助脚本初轮 E731/E501 已修复，无业务行为变化。

主动 LSP 检查 13 路径：**12 Markdown unavailable、1 Python inconclusive**（push-only 未确认 clean），不以 0 条输出宣称 LSP clean。session Python 缓存当前无 warning 不替代主动确认；最初 import missing 提示是原环境尚无候选包，导入/运行通过由两个隔离解释器直接提供证据。无需为消除该提示污染原 `.venv` 或改项目 LSP 配置。

## 4. 不依赖本机缓存的复跑（仅 Windows CPython 3.12）

在 main 仓库根运行，使用一个**新的** `.pi/artifacts/` 路径；不要清理/覆盖用户目录或原环境。网络只用于公开 wheel 下载，探针无 live 调用：

```powershell
$root = (Get-Location).Path
$trial = "$root/.pi/artifacts/nd-agent-02-c/replay"
New-Item -ItemType Directory -Force "$trial/tmp" | Out-Null
$env:TEMP = "$trial/tmp"
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:LANGCHAIN_TRACING_V2 = 'false'
$env:LANGSMITH_TRACING = 'false'
.venv/Scripts/python -B -m venv "$trial/venv"
$python = "$trial/venv/Scripts/python.exe"
$lock = 'evidence/agent-m03/nd-agent-02-c/candidate-win-py312.lock.txt'
& $python -B -m pip --isolated --disable-pip-version-check --no-cache-dir download --index-url https://pypi.org/simple --only-binary=:all: --require-hashes -r $lock -d "$trial/wheels"
& $python -B -m pip --isolated --disable-pip-version-check --no-cache-dir install --no-index --find-links="$trial/wheels" --only-binary=:all: --require-hashes -r $lock
& $python -B -m pip check
& $python -B -m pytest evidence/agent-m03/nd-agent-02-c/test_dependency_probe.py -q -p no:cacheprovider --basetemp="$trial/pytest"
```

首次依赖解析/锁生成辅助脚本与 wheelhouse 留在 `.pi/artifacts/nd-agent-02-c/`，未入库；正式发布需要批准的 resolver/build toolchain/角色与 Linux 锁，不能以 replay 绿灯代替审批。

## 5. 资料、结论与下一步

公开来源：[LangGraph 1.2.12](https://pypi.org/project/langgraph/1.2.12/)、[core 1.6.6](https://pypi.org/project/langchain-core/1.6.6/)、[openai adapter 1.6.7](https://pypi.org/project/langchain-openai/1.6.7/)、[checkpoint 4.2.0](https://pypi.org/project/langgraph-checkpoint/4.2.0/)、[Postgres Saver 3.1.2](https://pypi.org/project/langgraph-checkpoint-postgres/3.1.2/)、[Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)、[ChatOpenAI 文档](https://docs.langchain.com/oss/python/integrations/chat/openai)。安装 wheel 的版本内源码与实际探针优先用于精确语义；官网文档可能滚动，不替代锁定版本证据。persistence 网页本轮 fetch 失败，未据其作验收结论。

02-C review（非 done）；六项审核仍 pending，02-A/B/C 没有发布。原环境未新增包，runtime 不引用这组 probe；父票/02-D~H 仍 blocked。下一步先完成审核、Linux 锁验证与 02-B 映射签认，或独立编写 03-A 恢复 Contract proposed。全部 TBD-P0、DR-001/007/010/011、GATE 保持未关闭。

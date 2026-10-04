# 02-C Ubuntu 独立候选锁与双重建（pending）

- **日期 / 基线**：2026-10-04，main `3460a2f`，开场 clean。
- **状态**：Ubuntu 源码构建诊断环境的独立候选锁、双离线重建及技术探针完成；**不是** GitHub hosted CI、Actions 工具链、正式角色锁、供应链签认或 Agent/GATE 验收。
- **责任 / 范围**：M03 候选锁/manifest；M11 隔离验证、回归、证据；根进度与交接同步。未改业务源码、pyproject/正式锁、CI/Dockerfile/Compose、迁移、宿主源、主 `.venv` 或用户配置。
- **来源**：[原生执行单](linux-validation.md)、[Ubuntu 构建诊断](linux-ubuntu-tuna.md)、[变更记录](../../../progress/changes/20261004-M11-ubuntu-candidate-rebuild.md)。消费者/Owner/安全签认仍 pending。

## 1. 工具链与解析

| 项目 | 实测 / 限制 |
| --- | --- |
| 基础镜像 | Ubuntu 24.04，digest `sha256:a853f94d226358a79c740cfc7bce0c289748f3fe3488d921d038ccd752c61b60` |
| OS / glibc / 架构 | Ubuntu 24.04.5 / glibc 2.39 / x86_64；容器共享宿主内核，不用 Arch 解释器解析 |
| Python / pip | CPython 3.12.10，GCC 13.3.0；pip 25.0.1；复用上轮只读源码构建产物，不升级 |
| OpenSSL / SQLite | 3.0.13 / 3.45.1；stdlib 导入与 SQLite/bz2/lzma 往返通过 |
| 来源完整性 | Python 源码 SHA-256 与官方 HTTPS Sigstore bundle 摘要相符；完整签名链验证仍 pending |
| 系统运行库 | 临时 Ubuntu 容器内清华 HTTPS apt；保留 TLS、Ubuntu keyring 与包签名；实际版本留日志，不冒称 OS 锁 |

使用新容器 `pivot-ubuntu-lock-20261004` 和全新 `.pi/artifacts/nd-agent-02-c/linux-ubuntu-20261004/`，原产物目录只读。仓库只读挂载，新 artifact 目录单独可写；未传入宿主环境或真实供应商凭证。

从 Windows manifest 取 29 个 roots 与版本约束，以 PEP 503 规则规范化包名，在 Ubuntu 新 resolver venv **重新执行**清华 pip dry-run/only-binary 解析。没有复制 Windows/bookworm wheel 哈希作 Ubuntu 锁：

- 原生解析 **109 个非 yanked wheel**，全部精确版本与既有候选一致。
- 与 bookworm 包集合、版本及 wheel SHA-256 差异均 **0**；Windows-only 为 colorama/pywin32。
- 既有 bookworm 缓存只提供 wheel 字节，每个文件名与原始 SHA-256 均按本轮 Ubuntu report 独立核对后才使用。
- report 原始摘要 `6bae4afdce0896fbea8ba80e549313ff2254e8a4c690ab9a1264b1f68da928ab`，与上轮解析相同；本轮仍实际重新解析并留下独立日志。
- 按规范化包名排序后的锁文本摘要 `941eebb0bffe824d46e67655490be959d84f9ea494e6d5ff1f59d5da1d68a331`，UTF-8/LF；wheel hash 始终为原始字节摘要。

版本化 [候选锁](linux-ubuntu/candidate-linux-py312.lock.txt) 与 [manifest](linux-ubuntu/candidate-manifest.json) 明确 proposed/pending。manifest 附加源码工具链/镜像/镜像源/缓存来源信息，标记 `ubuntu-source-built-diagnostic-not-hosted-ci`，不隐式充当正式 CI 锁。

## 2. 离线重建、负向与探针

```bash
# 在上述 Ubuntu 容器中；trial 是仓库内新建 artifact 目录。
/trial/python/bin/python3.12 -B -m venv "$trial/verify"
/trial/python/bin/python3.12 -B -m venv "$trial/rebuild"
for name in verify rebuild; do
  "$trial/$name/bin/python" -B -m pip --isolated --disable-pip-version-check --no-cache-dir install \
    --no-index --find-links=/wheelhouse --only-binary=:all: --require-hashes \
    -r "$trial/candidate-linux-py312.lock.txt"
  "$trial/$name/bin/python" -B -m pip check
done
export LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false
export PIVOT_DEPENDENCY_PROBE_MANIFEST="$trial/candidate-manifest.json"
for name in verify rebuild; do
  "$trial/$name/bin/python" -B -m pytest -q \
    evidence/agent-m03/nd-agent-02-c/test_dependency_probe.py \
    evidence/agent-m03/nd-agent-02-c/test_budget_mapping_probe.py
done
"$trial/verify/bin/python" -B ops/run_grouped_tests.py --skip-web
```

两次安装均 `No broken requirements found`。xxhash 单包全零哈希 fixture 的 offline/dry-run/ignore-installed 检查 **exit 1**，明确报告 `THESE PACKAGES DO NOT MATCH THE HASHES`，不安装 fixture、不修改两个 venv。

| 环境 / 检查 | 结果 |
| --- | --- |
| verify 技术探针 | **20 passed，8.62s** |
| rebuild 技术探针 | **20 passed，6.47s** |
| 两环境 pip check | 均通过 |
| 错误哈希 dry-run | 预期 exit 1 / hash mismatch |

None 恢复 limit+2、strict 预格式化字典 passthrough、serde 保留 canary 与 Windows/bookworm 相符；这些仍须业务 BudgetGate/白名单承接，不表示 DR-010/011 关闭。

## 3. 完整 Python 回归

| 分组 | 结果 |
| --- | --- |
| Auth / Documents / Retrieval | 37 / 28 / 31 passed |
| QA/Run/SSE / Export-Audit / Worker | 79 / 26 / 79 passed |
| Contract / DB | 331 passed |
| Pipeline | **271 passed / 1 failed / 18 skipped** |
| Security ops / Performance | 2 passed / 11 passed + 1 skipped |
| ruff / compileall | passed |
| 合计 | **895 passed / 1 failed / 19 skipped** |

唯一失败为既有 `test_NFR_OBS_compose_staging_env_is_gitignored`（`tests/integration/pipeline/test_NFR_OBS_compose_staging.py:246`）：它要求根 `.env` 不存在，而本机已配置 gitignored `.env`。没有读取、删除、覆盖配置，也没有放宽/跳过测试；harness **exit 1**，不宣称全量绿。另有既有 Starlette/AnyIO DeprecationWarning。

首次 `docker run` 工具等待在 600 秒超时，容器仍运行。检查进程/日志确认继续执行，随后 `docker wait` 收到 **1**。最终 inspect 为 **exited / exit1 / running=false**，起止 UTC `2026-10-04T01:34:45.500839859Z` 至 `01:50:43.709922856Z`；未因为工具等待超时重跑或伪报 exit0。

## 4. 可复跑材料与未完成项

本轮忽略目录保留 validate.sh、runtime 包清单、environment、roots/versions-only、原生 report、生成日志、resolver/verify/rebuild、双 install/check/probes、错误哈希与完整回归日志。上轮 `/trial/python` 构建产物及 `/wheelhouse` 只读复用；新容器清华 apt 获取运行库，未改变宿主。版本化只归档文本候选和证据，不提交 venv/wheel/用户数据。

收尾检查：项目 `.venv/bin/python -B .pi/artifacts/nd-agent-02-c/linux-ubuntu-20261004/check_evidence.py` 验证版本化manifest与执行产物仅新增工具链/范围标记、109个原始wheel hash/锁/report/项目输入摘要一致；7份文档/89个本地链接/6个内嵌shell-Python块有效。validate.sh `bash -n`、`git diff --check`通过；主动LSP检查8个Markdown/JSON文件为8 clean/0 diagnostics，无unavailable/inconclusive。候选pytest9.1.1/ruff0.16.6版本未改，双venv已由锁一致性探针逐包验证。

复跑须用新目录/容器名，按 [执行单](linux-validation.md)重新解析，不能直接重复写入本轮目录。清华 source-built 诊断可复跑不等于批准 Actions artifact 替换；正式 CI 工具链仍需另验。

未运行 Web/Playwright、真实 PG/Saver/租约/恢复、live 模型、应用镜像 build/up 或 ECS。正式 Ubuntu CI/角色锁/构建工具、完整 Sigstore 验证、许可证/CVE/遥测及消费者/Owner 签认仍 pending。02-C **review**、0 ready / 5 review / 24 blocked 不变；02-D～H、DR-010/011、TBD-P0 与所有 GATE 不解锁。

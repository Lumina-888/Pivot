# 02-C 压缩 wheel 解压错误脱敏回归

- **日期 / 基线**：2026-10-04 / main `b84670a`，开场 clean。
- **Accountable**：M11；M03 仅同步候选验证进度。范围见[变更记录](../../../progress/changes/20261004-M11-candidate-compression-errors.md)。
- **性质**：既有离线核验工具缺陷修正，不是候选依赖发布、来源签认或 Agent 验收。
- **环境**：原项目 CPython 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / packaging 26.3；未安装新包。

## 1. Red 与最小修复

既有工具承诺材料错误返回脱敏 JSON，但 `ZipFile.read(METADATA)` 的 DEFLATE/LZMA 解压异常未归一化。合成 Fixture 使用标准库生成 wheel，分别破坏 DEFLATE 块类型、bzip2 签名、LZMA 属性，并重新计算 wheel/锁/manifest 摘要，确保实际到达解压路径，而非提前触发 hash mismatch。

```bash
.venv/bin/python -B -m pytest -q tests/security/ops/test_FR_AGENT_009_candidate_integrity.py \
  -k 'compressed_metadata or compression_cli'
```

首次结果 **4 failed / 5 passed / 56 deselected**：DEFLATE 抛出 `zlib.error`，LZMA 抛出 `LZMAError`；两种格式的函数和 CLI 用例失败，CLI stderr 有 traceback 与本机路径。bzip2 的损坏流已由现有 `OSError` 捕获，三个合法压缩格式正向测试均通过。

修复只在既有异常归一化边界补充 `ZlibError` / `LZMAError`，沿用 `unreadable_or_invalid_material` 和 `from None`。没有使用捕获全部 Exception 的方式，没有放宽 hash、路径或身份检查。9 个新增用例覆盖三种格式的正常读取、非法流拒绝与 CLI 输出；CLI 要求 exit 1、准确 JSON 和空 stderr。

## 2. 回归与静态检查

```bash
.venv/bin/python -B -m pytest -q tests/security/ops
.venv/bin/python -B ops/run_grouped_tests.py --skip-web
.venv/bin/python -B -m compileall -q \
  ops/check_candidate_integrity.py tests/security/ops/test_FR_AGENT_009_candidate_integrity.py
```

| 分组 | 结果 |
| --- | --- |
| Auth / Documents / Retrieval | 37 / 28 / 31 passed |
| QA/Run/SSE / Export-Audit / Worker | 79 / 26 / 79 passed |
| Contract / DB | 331 passed |
| Pipeline | 281 passed / 18 skipped |
| Security ops | 67 passed（候选工具65项 + 既有2项） |
| Performance | 11 passed / 1 skipped |
| 合计 | **970 passed / 19 skipped / 0 failed** |
| harness / ruff / compileall | exit 0 / passed / passed |

完整日志：`.pi/artifacts/nd-agent-02-c/compression-errors-20261004/grouped-tests.log`（忽略目录，不提交）。初次单独 ruff 发现异常 tuple 超100列，换行后完整 harness 静态检查通过。主动 LSP 检查两个 Python 改动文件 **2 clean / 0 diagnostics**。保留既有 Starlette/AnyIO 两条 DeprecationWarning，不为本刀升级无关依赖。

## 3. 真实候选材料只读复核

```bash
.venv/bin/python -B ops/check_candidate_integrity.py \
  --manifest evidence/agent-m03/nd-agent-02-c/candidate-manifest.json --project-root .
.venv/bin/python -B ops/check_candidate_integrity.py \
  --manifest evidence/agent-m03/nd-agent-02-c/linux-bookworm/candidate-manifest.json \
  --project-root . \
  --wheelhouse .pi/artifacts/nd-agent-02-c/linux-runtime-20261003-bookworm/wheels
.venv/bin/python -B ops/check_candidate_integrity.py \
  --manifest evidence/agent-m03/nd-agent-02-c/linux-ubuntu/candidate-manifest.json \
  --project-root . \
  --wheelhouse .pi/artifacts/nd-agent-02-c/linux-runtime-20261003-bookworm/wheels
```

Windows **111 项 consistent / wheel_bytes_checked=false**；bookworm/Ubuntu 各 **109 项 consistent / wheel_bytes_checked=true**。Ubuntu 复用已有缓存，每个字节按各自 manifest 哈希独立核验；不重新解析或复制锁。所有结果均明确 `not_dependency_approval`，材料/锁/manifest 未修改。

## 4. 限制与下一步

未下载、安装、提取或执行候选 wheel，未访问网络或改原环境、用户配置、业务、公开 Contract、pyproject、CI/镜像/迁移。未重跑目标候选容器、Hosted CI、Web/浏览器、真实 PG/Saver/恢复/租约、live 模型或 ECS。

本刀只保证已覆盖的损坏压缩流走脱敏失败路径，不声称完整 ZIP 安全、解压资源限额、来源认证、供应链批准或平台运行验收。正式 Ubuntu CI/角色锁/来源与安全审核、02-A/B/C 与恢复/持久化消费者和 Owner 签认仍 pending。02-C **review**、**0 ready / 5 review / 24 blocked**、02-D~H、DR-010/011、TBD-P0 与所有 GATE 均不解除；下一步仍是前置提案签认与批准验证环境。

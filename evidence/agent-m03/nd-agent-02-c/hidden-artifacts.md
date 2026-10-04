# ND-AGENT-02-C 隐藏目录证据归档回归

## 范围与环境

- 日期：2026-10-04；基线 `60a6455`，`main`，开场 clean。
- M11 修正 Ubuntu 手动候选 CI 的 artifact 选项与现有契约回归；M03 只同步进度。
- 本机 Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / PyYAML 6.0.3。
- 不修改业务、默认 CI、依赖/锁/manifest、迁移、镜像、主环境或用户配置。

## 根因与最小修复

固定版本 [upload-artifact README](https://github.com/actions/upload-artifact/blob/ea165f8d65b6e75b540449e92b4886f43607fa02/README.md#uploading-hidden-files) 明确：v4.4 起默认排除隐藏文件，隐藏目录中的普通文件也属于排除范围。既有 trial 位于 `.pi/`，上传没有设置 `include-hidden-files`，而 `if-no-files-found: warn` 允许无归档时步骤成功。

增加 `include-hidden-files: true`，保持仅本次 trial 顶层 `*.json` / `*.log` / `*.txt` 的非递归白名单；不扩大为 `.pi/**`，不上传 wheel、虚拟环境或配置。继续保留 always、7 天保留期、手动确认默认 false、只读权限和 Actions commit 固定。

## Red / Green

修改既有 `test_FR_AGENT_009_ci_workflow_artifacts_exclude_environments_and_wheels`，断言隐藏目录选项显式启用，同时保留原有路径和保留期断言。

```bash
.venv/bin/python -m pytest -q tests/security/ops/test_FR_AGENT_009_candidate_ci.py -k artifacts
```

Red：**1 failed / 60 deselected**，缺少 `include-hidden-files` 导致 `None is True` 失败；没有网络或 Hosted 上传。

修正工作流后：

```bash
.venv/bin/python -m pytest -q tests/security/ops
.venv/bin/python ops/run_grouped_tests.py --skip-web
```

- 安全组：**128 passed**，包含该上传契约回归及工作流 YAML/bash 语法检查。
- 首次完整 harness 的工具等待上限为180秒，前九组完成后超时；`pgrep` 确认无 harness/性能 pytest/ruff 遗留进程，不宣称本次 exit0。
- 第二次以420秒工具上限完整重跑：**1031 passed / 19 skipped / 0 failed**，harness **exit0**。
- 分组计数：auth37、documents28、retrieval31、QA/Run/SSE79、exports/audit26、worker79、contract/db331、pipeline281/18skip、安全128、performance11/1skip。
- harness 内完整 ruff 检查通过；api/worker/pipeline compileall 通过。
- pipeline 仍有2项已有 Starlette/httpx/anyio 弃用警告，未为本修复变更依赖。
- 对改动 Python 与 YAML 两路径主动 LSP：**2 clean / 0 diagnostics**。本地 YAML 风格 runner 曾报告长行；核对 HEAD 已有32处超过80字符，本轮最终未增加长行，不宣称所有风格 runner 全 clean。

## 限制与下一步

本轮验证的是配置契约与本机回归，不是 GitHub runner 上的真实文件发现或上传结果。未推送/dispatch、未运行 Hosted CI/目标候选/Web/PG/Saver/live/镜像；没有冻结参数或代签审批。

02-C review、0 ready / 5 review / 24 blocked、全部消费者/Owner签认及 DR-010/011/TBD-P0/GATE 不变。下一步经 Owner 审查并批准待验证 ref 和手动 CI，检查真实 run 的原生环境、双离线重建、负向/探针/回归及可下载 artifact。

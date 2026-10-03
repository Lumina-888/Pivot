# 2026-10-03 本机 Linux 开发环境证据

## 范围与授权

- 输入基线：main `8782c7c`，开场工作区 clean，相对本地 origin/main 领先 190；未 fetch/push。
- 用户授权配置这台电脑供 Pivot 开发，并将默认下载渠道设为清华。仅授权本机开发环境，不代签 Agent Contract、供应链审核或生产许可。
- M11 负责开发环境与验证；M03 记录 Python 环境；M00 仅同步恢复入口。没有修改业务源码、公开 schema、pyproject、正式锁、CI/Dockerfile、迁移或 TBD-P0。
- 可复用操作见 [Linux runbook](../ops/runbook-local-linux.md)，变更边界见 [环境变更记录](../progress/changes/20261003-M11-local-linux-environment.md)。

## 环境与配置

- Arch/Omarchy x86_64，Linux 7.2.5-3-omarchy，GCC 16.2.1；系统 Python 3.14.7 未替换。
- 独立 CPython 3.12.10，OpenSSL 3.6.4；SSL/sqlite3/bz2/lzma/ctypes/readline/venv 导入通过。缺省构建缺可选 tkinter，不影响此 Web 项目；不是全量 CPython 上游测试或安全审核。
- Python 源码：清华 HTTPS Python 镜像，3.12.10 tar.xz；官方 python.org HTTPS 发布页 MD5 `0c0a6cce86d7611aed691d61e0599de0` 校验一致，实际 SHA-256 `07ab697474595e06f06647417d3c7fa97ded07afc1a7e4454c5639919b46eaea` 已记录。未作 GPG/Sigstore 签名验证，不宣称独立供应链签认。
- Node 26.8.2 / npm 11.19.1；Docker client/server 29.7.2 / Compose 5.5.1；Playwright 1.63.0、Chromium v1243（153.0.8010.12）。Arch 非官方支持平台，使用官方 Ubuntu 24.04 fallback 并实际跑浏览器测试。
- pip 用户默认源为清华 HTTPS；Arch 首选清华，保留原三个源，备份 `/etc/pacman.d/mirrorlist.pivot-backup-20261003-131809`。Omarchy 独立仓库、npm 官方 registry 和 Playwright CDN 未改。
- `.venv` 按已发布 extras/契约依赖安装；采用原 Windows manifest 中 62 项 unchanged_baseline **版本约束**，未使用其 wheel 哈希。没有安装 Agent roots，`find_spec('langgraph') is None` 验证通过。当前宿主安装清单保存为私有 artifact，不是正式 Linux 锁。
- Docker 已 enable/start，用户 docker 组已登记，用 `newgrp docker -c 'docker version ...'` 验证新组权限；旧登录会话不自动获得补充组。
- Git 初次文档提交因缺 user.name 失败；仅在当前仓库设置显示名为实际登录用户 `lumina888`，沿用原全局邮箱、不写入证据，不改全局身份。
- 创建两个 loopback 用户级服务（未开机启用）、私有 mode-600 `.env`、忽略的 `web/.env.local`；随机登录口令/Token secret 不写证据。配置只用于低敏 fixture，memory 状态重启即丢失，无真实模型或文档外发。

## 实际验证

| 命令/检查 | 结果 |
| --- | --- |
| `.venv/bin/python -m pip config get global.index-url` | 清华 `https://pypi.tuna.tsinghua.edu.cn/simple` |
| `.venv/bin/python -m pip check` | No broken requirements found |
| `ops/run_grouped_tests.py` 的十组 Python | 661 passed / 19 skipped；M05 79；pipeline 272 passed / 18 skipped；全部 Python 组已执行完 |
| 同一 harness 的 ruff / compileall | passed |
| `npm --prefix web ci --no-audit --no-fund` | 334 packages installed；lock 未改 |
| Web foundation / user / admin | 18 / 13 / 8 passed |
| Web typecheck / lint | passed；无 ESLint 警告/错误 |
| `.venv/bin/playwright install chromium` | Chromium/Headless Shell/FFmpeg 下载完成 |
| `.venv/bin/python ops/run_playwright_login.py` | 11 passed；实际启动本机 uvicorn/Next/Chromium；未启动 Compose |
| 运行中本地服务 smoke | health/login/native PDF 上传后 ready/无证据 refused/SSE 通过 |
| `/readyz` | 真实 503/not_ready；postgres/minio/qdrant/redis 全 false，未绕过 |
| 文档同步后公共契约回归 | `tests/contract --ignore=tests/contract/stream`：48 passed |
| 文档静态检查 | `git diff --check` passed；主动 LSP 8 Markdown 文件 clean，无 unavailable/inconclusive |
| 默认 memory 搜索 | 空结果；未接真实索引，不验收 RAG 闭环 |

原始日志/辅助脚本/源码构建产物在 `.pi/artifacts/local-linux-20261003/`（忽略）：`grouped-tests.log`、`playwright.log`、`local-smoke-final.log`、`installed-baseline.txt`、Python configure/build/install 日志、`compose-pull.log`。源归档与虚拟环境不是正式发布 artifact。

## 失败与限制

1. `mise install python@3.12.10` 因 GitHub/pyenv 连接超时失败；随后采用清华的官方源码用户级构建，没有替换系统 Python。首次编译 600s 窗口到期，检查无残留构建进程后增量 make 成功，install 与模块验证通过。
2. 整个 grouped harness 的 300s 窗口在 npm ci 阶段到期；十组 Python、ruff/compileall 已全部完成，**不宣称单次完整 harness exit 0**。后续独立 npm ci 与五个 Web 检查均通过。
3. npm 11 提示 esbuild/unrs-resolver 安装脚本待审核；没有 blanket approve、ignore-scripts 或改依赖来绕过。现有 Web 测试/编译器/lint/Next 浏览器启动实际通过。旧 Node module.register 弃用、Starlette/httpx 和 AnyIO 警告保留。
4. 本机 API 配置最初误把 export public base 设为 loopback，被现有 signer 拒绝。改用已有 `https://files.pivot.test` fixture，不改安全逻辑；真实签名下载服务仍不存在。
5. 初次运行 smoke 发现 `/readyz` 503、memory 搜索为空；记录真实状态后仅验证该环境的无证据拒答，不修改业务或已有测试，不伪称 readiness/RAG 通过。
6. 官方 Docker Hub 拉取四个 fixture 镜像失败：直连 registry i/o timeout。通过现有 Clash 127.0.0.1:7897 访问官方 `/v2/` 返回预期 401，但 daemon proxy 的两次 pkexec 分别等待 120s/180s 超时，未生成系统 drop-in。四个容器未启动；须 Owner 完成系统授权。
7. 未装 Agent 框架/候选环境，未执行候选依赖 20 probes/原生锁双重建、真实 PG 迁移/容器健康、持久恢复、live/ECS、生产压测或供应链/CVE 审核。02-A/B/C review、D~H blocked、DR-010/011/TBD-P0 和全部 GATE 不变。

本轮只是本机开发/测试可用，真实存储联调环境仍未完成。Markdown 的依据为主动 LSP 8 文件明确 clean outcome（并非空缓存）；系统配置不宣称经 LSP 验证，现有源码静态依据是实际 ruff/compileall 与 Web typecheck/lint。

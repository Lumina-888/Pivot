# 02-C Debian bookworm 原生候选锁（pending）

- **日期 / 状态**：2026-10-03；bookworm runtime 候选验证完成，**不是**正式锁、Ubuntu CI 锁、镜像构建验收、供应链签认或 Agent/GATE 通过。02-C 仍 review。
- **基线**：main `93f7e50`，开场 clean。未改 pyproject、正式锁、CI、Dockerfile、业务源码、迁移或生产默认。
- **责任**：M03 候选解析/锁，M11 容器验证与回归。M01 许可证/CVE、M00 归档与消费者/Owner 签认仍 pending。
- **执行单**：[linux-validation.md](linux-validation.md)。本轮只完成其中 Debian bookworm runtime 一半；Ubuntu CI 仍未执行。

## 1. 环境

| 项 | 值 |
| --- | --- |
| 宿主 | Arch/Omarchy x86_64，glibc 2.44；**不**作为锁平台 |
| 容器 | `python:3.12.10-slim-bookworm` |
| 镜像 digest | `sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db` |
| 容器 OS | Debian 12 bookworm，glibc 2.36，x86_64 |
| Python / pip | CPython 3.12.10（GCC 12.2.0），pip 25.0.1（镜像自带，未 upgrade） |
| 拉取 | 官方 Hub 直连超时；本机 Clash `127.0.0.1:7897` 未监听。经 `docker.m.daocloud.io/library/python` 拉取，digest 与官方 tag 记录对照，不是未知镜像站替换内容 |

容器内核仍是宿主 `7.2.5-3-omarchy`。这是容器验证，不证明 API 镜像构建、角色锁或独立 Debian 机器。

## 2. 解析与材料

输入为 Windows [candidate-manifest.json](candidate-manifest.json) 的 29 个 roots 与 111 个版本约束。约束名按 pip 规范小写，**版本不变**；不复制 Windows wheel 哈希。

首次 `pip install --dry-run --only-binary=:all:` 因 `SQLAlchemy` 与约束名 `sqlalchemy` 被 pip 25.0.1 当成两次请求而 `ResolutionImpossible`。只规范化约束名后，官方 `https://pypi.org/simple` 解析成功：109 个非 yanked wheel，`sys_platform=linux`。

与 Windows 候选按规范化包名对比：

- 版本差异：**0**。
- Linux 不需要、Windows 有：`colorama==0.4.6`、`pywin32==312`。
- 规范化后没有 Linux 独有包。报告里的 `pydantic_core` / `typing_extensions` / `uuid_utils` / `et_xmlfile` / `prompt_toolkit` 只是与 Windows 清单的连字符/下划线命名不同。
- 28 个包的 wheel 文件名不同，均为 manylinux/abi3 对 win_amd64；哈希独立计算。

官方 `files.pythonhosted.org` 下载读超时。随后用已配置的清华 HTTPS `https://pypi.tuna.tsinghua.edu.cn/simple`，仍带 `--require-hashes`，下载 109 个 wheel。逐个原始 SHA-256 与官方解析报告一致。

可重跑材料：

- [candidate-linux-py312.lock.txt](linux-bookworm/candidate-linux-py312.lock.txt)
- [candidate-manifest.json](linux-bookworm/candidate-manifest.json)
- 原始 report、双 venv、wheelhouse 与日志留在忽略目录 `.pi/artifacts/nd-agent-02-c/linux-runtime-20261003-bookworm/`，不入库。

## 3. 离线重建、负向与探针

两个全新 venv（verify、rebuild）均 `--no-index --find-links --only-binary=:all: --require-hashes` 安装，`pip check` 均为 `No broken requirements found`。

篡改单个 `xxhash` 哈希后，`pip install --dry-run --ignore-installed --no-index --require-hashes` **exit 1**，日志明确 `THESE PACKAGES DO NOT MATCH THE HASHES`（期望全零，实际 `237b8f63…`）。未安装该 fixture。

`PIVOT_DEPENDENCY_PROBE_MANIFEST` 指向本次 Linux manifest 后：

| 解释器 | 结果 |
| --- | --- |
| verify | `test_dependency_probe.py` + `test_budget_mapping_probe.py`：**20 passed**（13.35s） |
| rebuild | 同样两文件：**20 passed**（13.13s） |

首次探针 19 passed / 1 failed，是因为 manifest 挂在容器 `/trial`，不在仓库根内，`Path.is_relative_to` 拒绝。改挂仓库内 `.pi/artifacts/...` 后通过。这不放宽探针。

verify 解释器执行 `ops/run_grouped_tests.py --skip-web`：

- auth 37、documents 28、retrieval 31、QA/Run/SSE 79、export/audit 26、worker 79、契约/DB 331、ops 2、perf 11 passed / 1 skipped。
- pipeline **271 passed / 1 failed / 18 skipped**。失败仅为 `test_NFR_OBS_compose_staging_env_is_gitignored`：仓库根已有 gitignore 的 `.env`（mode 600）。未读取、删除或放宽测试。
- ruff、compileall passed。
- 合计 **895 passed / 1 failed / 19 skipped**。不宣称全量绿或 harness exit 0。

None 恢复的 limit+2、strict 字典 passthrough、serde 保留 canary 仍由探针锁定，须由业务 BudgetGate/白名单承接。不关闭 DR-010/011。

## 4. 未完成

- Ubuntu CI 原生锁未跑。GitHub `ubuntu-latest` 只声明 Python 3.12，不是本轮 3.12.10/bookworm 锁。
- 未 build/up 项目镜像，未审核许可证/CVE/遥测，未跑真实 PG、live、Web 或 Compose。
- 主 `.venv` 仍无 LangGraph；候选只存在于忽略的容器 venv。
- 02-A/B/C、03-A、04-A 仍 review；0 ready / 5 review / 24 blocked。本文件不代签、不发布依赖、不解除 02-D～H。

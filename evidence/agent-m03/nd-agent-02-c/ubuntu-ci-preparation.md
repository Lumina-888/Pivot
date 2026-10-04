# 02-C Ubuntu 手动候选 CI 入口准备证据

- **日期 / 基线**：2026-10-04；main `4fb1693`，开场 clean。
- **范围**：用户确认继续 02-C 正式 Ubuntu CI 验证准备。M11 新工作流、准备工具、bootstrap 候选锁、安全测试/证据；M03 模块进度，根/交接同步。见 [实施范围](../../../progress/changes/20261004-M11-candidate-ubuntu-ci-preparation.md)。
- **结论**：版本化手动入口与本地正负向检查完成；**未推送、未触发 Hosted CI、未生成 Hosted CI passed 证据**。现有 Ubuntu 源码诊断候选仍不是 Hosted CI，02-C review 不变。
- **未改动**：默认 `ci.yml`、api/worker pyproject、既有候选锁/manifest、业务/公开 Contract/迁移/镜像、主 `.venv`、用户配置。无真实模型、PostgreSQL、Compose 或 ECS 调用。

## 1. 交付与边界

- [candidate-ubuntu.yml](../../../.github/workflows/candidate-ubuntu.yml)：仅 `workflow_dispatch`，确认项默认 false，必须明确为 true 才执行；Ubuntu 24.04/x64、Python 3.12.10、40 分钟 job deadline；contents:read、checkout 不保留凭证，三个 Actions 固定 commit。
- [prepare_candidate_ci.py](../../../ops/prepare_candidate_ci.py)：原生环境前检、只导出版本的 roots/constraints、新输出目录限制；验证 pip report 平台/包集合/版本/轮子/hash 与既有原生 Ubuntu 候选一致，拒绝漂移/yanked/非官方 URL/重复包/畸形 JSON。生成本轮独立 proposed/pending manifest/锁，不复制 Windows wheel 哈希；记录 report 原始摘要、项目输入/源清单摘要及有限 runner provenance。环境变量中的 GitHub 字段只是 provenance，不是审批真实性证明。
- [ci-bootstrap.lock.txt](ci-bootstrap.lock.txt)：仅隔离 driver 的 packaging 26.3，摘要与既有 Ubuntu proposed 候选一致；CPython 3.12.10 ensurepip 的 pip 25.0.1 必须检查，不升级。此文件不是角色/生产锁。
- [安全测试](../../../tests/security/ops/test_FR_AGENT_009_candidate_ci.py)：公共准备/报告/CLI 边界使用合成文件、显式有限环境 Fixture；工作流通过 YAML 解析、固定安装/触发/artifact 契约与每个 run block 的 `bash -n` 检查。没有 mock Pivot 图/供应商验收。

工作流依次做：隔离 driver → 原生 dry-run report → 独立哈希锁 → require-hashes 下载与只读 wheel 身份核验 → verify/rebuild 两个全新 venv 离线 hashes 安装/pip check/各 20 技术探针 → 单包错误哈希 dry-run 必须失败且包含 hash mismatch 分类 → 旧 Python 分组与静态检查。任一正向步骤失败即停止；负向用例不接受其他网络/文件失败冒充 hash mismatch。

失败时也上传 trial 顶层 `*.json/*.log/*.txt`；不递归上传 wheelhouse/venv/用户配置。7 天是本候选诊断 artifact 的显式保存范围，不是业务 checkpoint/文档保留策略。Hosted runner image 会变化，记录实际 ImageOS/ImageVersion/kernel；精确系统库锁、Actions/Python 完整来源签名和角色/镜像构建仍未验收。

## 2. Red → Green

1. 初始准备接口缺工具：1 error → 1 passed。
2. roots 负向暴露空数组、pip directive/直接 URL、未知包、不兼容版本/换行输入：6 failed/13 passed → 19 passed；不因非法输入创建试验目录。
3. 原生 report 接口未实现：1 failed/19 passed → 20 passed。
4. 平台/包/hash/URL/yanked 漂移、已有输出覆盖、源材料变化、report/environment symlink 越界：25 failed/20 passed → 45 passed。
5. CLI/手动 workflow 未接入：1 failed/45 passed/3 errors → 49 passed。
6. 严格 JSON/非字符串 URL/源 symlink/bootstrap 身份：整数 URL 导致未归一化 AttributeError，1 failed/60 passed → 增加字符串类型门禁后 **61 passed**；NaN/Infinity/重复键不放行。

所有错误只返回有限分类，不打印供应商 URL、原始错误、traceback 或输入路径。既有 checker 的 hash/授权状态/路径规则未放宽。未增加 ignore 注释或跳过新增用例修绿。

## 3. 本地验证

本机 Arch；CPython **3.12.10** / pip **25.0.1** / pytest **9.1.1** / ruff **0.16.6** / packaging **26.3** / PyYAML **6.0.3**，原 `.venv` 未安装新包。

| 命令（仓库根） | 实际结果 |
|---|---|
| `.venv/bin/python -m pytest tests/security/ops -q` | **128 passed**：新 CI 61 + 既有 67 |
| `.venv/bin/python ops/run_grouped_tests.py --skip-web` | **1031 passed / 19 skipped / 0 failed**；harness exit 0，ruff/compileall passed |
| `.venv/bin/python -B -m compileall -q ops/prepare_candidate_ci.py tests/security/ops/test_FR_AGENT_009_candidate_ci.py` | passed |
| 主动 LSP：新工具、安全测试、工作流 YAML 三路径 | 3 clean / 0 findings / 0 unavailable / 0 inconclusive |
| `.venv/bin/python -B ops/prepare_candidate_ci.py --stage prepare --trial .pi/artifacts/nd-agent-02-c/local-ci-preflight-20261004` | 预期 exit 1，stdout 仅 `{"status":"invalid","category":"native_environment"}`；本机 Arch 不是 Ubuntu 验收目标 |
| `test ! -e .pi/artifacts/nd-agent-02-c/local-ci-preflight-20261004` | exit 0，前检拒绝后无试验输出 |
| 原 `.venv` 的 `importlib.util.find_spec("langgraph")` | None，未接入/安装正式 Agent |

分组：M01 37、M02 28、M04 31、M05 79、M06 26、M07 79、M00/M03 331、pipeline 281/18skip、ops 128、performance 11/1skip。既有 Starlette/httpx 与 anyio 的两条弃用警告保留，不升级依赖修警告。

Ruff 初次检查仅测试 imports 排序 I001，调整后 harness 全部通过。`actionlint` 本机未安装，未安装新工具；没有 actionlint 或远端语义执行成功声明。YAML/本地 shell 语法检查不替代 Hosted runner 运行。

Actions 固定引用通过公开 `git ls-remote` 核对：

| 公开 tag | 实测 commit |
|---|---|
| actions/checkout v4.2.2 | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| actions/setup-python v5.6.0 | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| actions/upload-artifact v4.6.2 | `ea165f8d65b6e75b540449e92b4886f43607fa02` |

这些公开 ref 绑定不证明签名/供应链批准；没有发送项目内容、企业文档或秘密，没有读取远端凭证。

## 4. 实际运行与后续

本轮只提交入口，不推送/dispatch。工作流文件须先经 Owner 审查并出现在远端默认分支，再在 GitHub Actions 选择 `candidate-ubuntu` / Run workflow，明确选定待验证 ref、勾选 `confirm_candidate_only`。确认项批准该次技术候选验证，不是 Contract/生产依赖批准。

首次远端运行后须归档 run URL、输入 commit、实际 ImageOS/ImageVersion/Python 来源、完整步骤结果、两环境 probes/回归/负向日志及独立 manifest/锁。失败保持 blocked/review；不能用本地合成 report 或 Arch 回归替代。不要自动合并生成锁或改变正式 pyproject。

**仍待处理**：02-A/B/C 消费者/Owner 签认、正式 Ubuntu CI 执行、角色锁/构建工具/系统库/镜像、来源签名/许可证兼容/CVE/遥测/内嵌库审核。03-A/04-A 及 DR-010/011 独立待签，预算生产数值 TBD-P0。0 ready/5 review/24 blocked、02-D～H 与全部 GATE 不变。

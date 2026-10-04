# 02-C 离线候选材料一致性工具

- **日期 / 基线**：2026-10-04 / main `fa291b2`，开场 clean。
- **责任**：M11 验证工具/安全测试/证据；M03 Windows manifest 补齐锁文件名与候选进度；根进度/交接同步。
- **范围记录**：[变更记录](../../../progress/changes/20261004-M11-candidate-integrity-tool.md)。
- **性质**：只读离线证据一致性检查，不安装或执行候选 wheel，不发布依赖，不验证业务 Agent，也不代签供应链/Owner/消费者。

## 1. 交付与边界

新增版本化入口 [check_candidate_integrity.py](../../../ops/check_candidate_integrity.py)，不再依赖 `.pi/` 临时复核脚本：

- 拒绝重复 JSON 键、非 JSON 的 NaN/Infinity 常量、不完整材料、非 proposed/pending 状态、非严格单版本/单哈希锁条目及重复规范化包名。
- 核验 UTF-8/LF 锁摘要、manifest/锁完整集合、wheel 文件名包名/版本及三份固定项目输入摘要；不因宿主不同而选择或更改候选锁。
- 拒绝任意项目输入路径、锁/wheel 路径分隔符及越界 symlink；错误不回显材料、用户路径或底层异常。
- `--wheelhouse` 可选，逐个流式核验原始 wheel SHA-256，ZIP 内唯一根 `.dist-info/METADATA` 的 Name/Version；不提取、不导入、不执行 wheel，不读取供应商配置/密钥，不访问网络。
- 成功 JSON 明确 `approval=not_dependency_approval` 与 `wheel_bytes_checked`。不传 wheelhouse 时只验证材料，不冒称核验了文件字节。

工具使用现有 pytest 工具链的 `packaging`（本机 26.3），未新增或安装依赖。Windows manifest 原先没有 `candidate_lock_file`，补齐为 `candidate-win-py312.lock.txt`；所有候选版本、wheel/锁哈希和其余字段保持不变。工具拒绝字段缺失，不推断或 fallback。

这不是依赖闭包解析、平台运行验证、来源签名、许可证/CVE/遥测审核或文件系统沙箱。校验给定材料的一致性不证明材料本身可信；候选仍需要原审批流程。未读取未知任意 ZIP 路径或提取文件；本轮只对已捕获、哈希相符的公开 wheel 做静态检查。

## 2. Red / Green

新增 [安全测试](../../../tests/security/ops/test_FR_AGENT_009_candidate_integrity.py) **56 项**：合成临时输入/锁/wheel 的合法与篡改、遗漏、非法 schema、重复项、包集合/哈希/版本差异、锁/wheel/项目输入路径及 symlink、JSON 重复键、CLI 脱敏与成功不改 pending，以及三份实际候选材料回归。

```bash
.venv/bin/python -m pytest -q tests/security/ops/test_FR_AGENT_009_candidate_integrity.py
.venv/bin/python -m pytest -q tests/security/ops
```

- 首次 Red：工具不存在，明确 `FileNotFoundError`，收集 exit 2 / 1 error。
- 首次实现：41 passed / 1 failed，Windows manifest 缺少锁文件名。
- 补齐真实证据元数据：42 passed；增加 11 个边界测试后53 passed。提交前新增 NaN/Infinity/-Infinity 负向测试 **3 failed**（标准解析器默认放行），显式 `parse_constant` 拒绝后，最终新增测试 **56 passed**，M11 安全组含原 2 项为 **58 passed**。
- LSP 首次提示 4 项类型收窄问题，改用显式类型/空值分支；最终主动检查两份 Python 文件 **2 clean / 0 diagnostics**。

## 3. 实际离线复核

```bash
.venv/bin/python ops/check_candidate_integrity.py \
  --manifest evidence/agent-m03/nd-agent-02-c/candidate-manifest.json \
  --project-root .

.venv/bin/python ops/check_candidate_integrity.py \
  --manifest evidence/agent-m03/nd-agent-02-c/linux-bookworm/candidate-manifest.json \
  --project-root . \
  --wheelhouse .pi/artifacts/nd-agent-02-c/linux-runtime-20261003-bookworm/wheels

.venv/bin/python ops/check_candidate_integrity.py \
  --manifest evidence/agent-m03/nd-agent-02-c/linux-ubuntu/candidate-manifest.json \
  --project-root . \
  --wheelhouse .pi/artifacts/nd-agent-02-c/linux-runtime-20261003-bookworm/wheels
```

三条命令均 exit 0 / `consistent` / `not_dependency_approval`。Windows 111 项只核验版本化材料（`wheel_bytes_checked=false`）；bookworm 与 Ubuntu 各 109 项实际核验既有缓存 wheel 原始字节和 METADATA（`true`），未重新解析或下载。Ubuntu 与 bookworm 文件相同仅作一致性复核，不冒称重新执行目标平台 resolver。

## 4. 回归与限制

环境：原项目 `.venv`，CPython **3.12.10**、pytest **9.1.1**、ruff **0.16.6**、packaging **26.3**；未修改主环境。

```bash
.venv/bin/python ops/run_grouped_tests.py --skip-web
.venv/bin/python -m ruff format --config api/pyproject.toml \
  ops/check_candidate_integrity.py tests/security/ops/test_FR_AGENT_009_candidate_integrity.py
.venv/bin/python -m compileall -q \
  ops/check_candidate_integrity.py tests/security/ops/test_FR_AGENT_009_candidate_integrity.py
git diff --check
```

完整十组 **961 passed / 19 skipped / 0 failed**，harness exit 0。Auth37 / Documents28 / Retrieval31 / QA-Run-SSE79 / Export-Audit26 / Worker79 / Contract-DB331 / Pipeline281+18skip / Security58 / Performance11+1skip。ruff 与 compileall 通过；pipeline 两项已有 Starlette/AnyIO DeprecationWarning 保留，未升级依赖修警告。

未重跑目标候选容器/20框架探针、正式 Ubuntu Hosted CI、Web/Playwright、真实 PG/Saver/租约/恢复、live 模型或应用镜像。未改业务、pyproject、锁文件、公开契约、CI/Dockerfile/Compose、迁移、宿主/用户配置；Windows manifest 只增加锁文件名。

**02-C review、0 ready / 5 review / 24 blocked 不变。** 正式 Ubuntu CI/角色锁/构建来源、安全与消费者/Owner 签认仍 pending；本轮不解除 02-D～H、DR-010/011、TBD-P0 或任何 GATE。

# 02-C 原生 Linux 验证执行单（尚未执行）

- **状态**：部分执行。2026-10-03 Debian bookworm runtime 候选已完成，见 [linux-bookworm.md](linux-bookworm.md)；Ubuntu CI 仍未执行。本文件不是完整 Linux 测试报告或正式锁。
- **责任**：M03 候选解析/锁，M11 环境/回归/镜像，M01 供应链审查，M00 归档，Owner 提供或批准环境。
- **前置记录**：[02-A/B/C 审核与签认清单](../nd-agent-02-abc-review.md)。不得复制 Windows wheel 哈希、用宿主 `pip --platform` 冒充原生 Linux，或自行启用 WSL/安装 Docker/使用未知 SSH 主机。

## 1. 环境与输出

先取得批准的 Linux x86_64 CPython 3.12.10 环境（Debian bookworm runtime 与 Ubuntu CI **分别**执行）。记录 OS、glibc、架构、Python/pip 与镜像 digest（容器时）。Native venv 验证不自动证明 API 镜像构建；镜像/角色锁/构建工具/许可证/CVE 仍独立审核。

在获准 Linux 仓库根执行以下命令；新建唯一的 `.pi/artifacts/nd-agent-02-c/linux-<scope>-<run-id>/`，不复用或清理旧目录。下载只访问公开 PyPI，不调用模型/PG/Compose/ECS。

```bash
set -euo pipefail
# 将 run-id 换成此次唯一 ID，CI/runtime 分别选 scope。
trial="$PWD/.pi/artifacts/nd-agent-02-c/linux-runtime-run-id"
test ! -e "$trial"
mkdir -p "$trial/tmp"
export TMPDIR="$trial/tmp" TEMP="$trial/tmp" TMP="$trial/tmp"
export PYTHONDONTWRITEBYTECODE=1
export LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false
export PYTHONPYCACHEPREFIX="$trial/pycache"
export PYTEST_ADDOPTS="-p no:cacheprovider --basetemp=$trial/pytest"
export RUFF_CACHE_DIR="$trial/ruff-cache"
export TRIAL="$trial"
python3.12 -B -c 'import platform,sys; assert sys.platform == "linux"; assert platform.machine() == "x86_64"; assert sys.version_info[:3] == (3,12,10)'
python3.12 -B -m venv "$trial/resolver"
py="$trial/resolver/bin/python"
# 工具链须预先受控提供；不默默 upgrade pip。
"$py" -B -c 'import importlib.metadata as m; assert m.version("pip") == "25.0.1"'
uname -a > "$trial/environment.txt"
"$py" -B -m pip --version >> "$trial/environment.txt"
```

以下仅导出**版本约束**，不复制 Windows artifact 哈希。constraints 不要求 Linux 安装 colorama 等 Windows-only 项；Linux marker/额外闭包必须由本机 resolver 计算。新增/缺失/变化包都列入差异审查，不能要求 Linux 恰好 111 项。

```bash
"$py" -B - <<'PY'
import json, os
from pathlib import Path
trial = Path(os.environ['TRIAL'])
source = json.loads(Path('evidence/agent-m03/nd-agent-02-c/candidate-manifest.json').read_text())
(trial/'roots.txt').write_text('\n'.join(source['roots'])+'\n', encoding='utf-8')
(trial/'versions-only.txt').write_text('\n'.join(p['name']+'=='+p['version'] for p in source['packages'])+'\n', encoding='utf-8')
PY
"$py" -B -m pip --isolated --disable-pip-version-check --no-cache-dir install \
  --dry-run --ignore-installed --only-binary=:all: --index-url https://pypi.org/simple \
  -r "$trial/roots.txt" -c "$trial/versions-only.txt" --report "$trial/resolve-report.json" \
  > "$trial/resolve.log" 2>&1
```

解析失败即保存日志/blocked，不删除 constraints、改版本或降为 sdist 来修绿。成功后按原生 report 生成本次独立候选材料：

```bash
"$py" -B - <<'PY'
import hashlib, json, os
from pathlib import Path
from urllib.parse import unquote, urlparse
trial = Path(os.environ['TRIAL'])
source = json.loads(Path('evidence/agent-m03/nd-agent-02-c/candidate-manifest.json').read_text())
report = json.loads((trial/'resolve-report.json').read_text())
assert report['environment']['sys_platform'] == 'linux'
packages = []
for item in report['install']:
    url = urlparse(item['download_info']['url'])
    wheel = unquote(Path(url.path).name)
    assert url.scheme == 'https' and url.hostname == 'files.pythonhosted.org'
    assert wheel.endswith('.whl') and not item.get('is_yanked', False)
    md = item['metadata']
    digest = item['download_info']['archive_info']['hashes']['sha256']
    assert len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)
    packages.append({'name': md['name'], 'version': md['version'], 'wheel': wheel, 'sha256': digest,
                     'requires_python': md.get('requires_python'), 'requires_dist': md.get('requires_dist', [])})
packages.sort(key=lambda p: p['name'].lower())
lock = '\n'.join(p['name']+'=='+p['version']+' --hash=sha256:'+p['sha256'] for p in packages)+'\n'
lock_name = 'candidate-linux-py312.lock.txt'
(trial/lock_name).write_text(lock, encoding='utf-8')
inputs = {p: hashlib.sha256(Path(p).read_text(encoding='utf-8').encode()).hexdigest()
          for p in source['project_input_sha256']}
# 保留 report 原始 bytes 摘要；此 manifest 仍是 pending 候选。
manifest = {'status': 'proposed', 'approval': 'pending', 'environment': report['environment'],
            'pip_version': report['pip_version'], 'roots': source['roots'], 'packages': packages,
            'candidate_lock_file': lock_name, 'text_hash_normalization': 'UTF-8 text with LF line endings',
            'candidate_lock_sha256': hashlib.sha256(lock.encode()).hexdigest(),
            'project_input_sha256': inputs,
            'resolve_report_sha256': hashlib.sha256((trial/'resolve-report.json').read_bytes()).hexdigest()}
(trial/'candidate-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
PY
lock="$trial/candidate-linux-py312.lock.txt"
"$py" -B -m pip --isolated --disable-pip-version-check --no-cache-dir download \
  --index-url https://pypi.org/simple --only-binary=:all: --require-hashes \
  -r "$lock" -d "$trial/wheels" > "$trial/download.log" 2>&1
```

## 2. 两次离线重建、负向哈希与回归

- 两个全新 venv（verify/rebuild）用 `--no-index --find-links="$trial/wheels" --only-binary=:all: --require-hashes -r "$lock"` 安装；每个执行 `pip check`。
- 实际 wheel 原始 SHA-256 与 manifest 相符；删除/篡改哈希的**单包 Fixture**在 `pip install --dry-run --ignore-installed --no-index ... --require-hashes` 必须非零退出并明确报 hash mismatch（其他网络/文件错误不算通过）。仅 dry-run，不修改已安装环境。
- 两个解释器均运行下面全部技术探针，Linux 必须显式指定原生 manifest；不能跳过锁一致性测试。`PIVOT_DEPENDENCY_PROBE_MANIFEST` 只用于显式 evidence probe，不是 Agent 运行配置。

```bash
export PIVOT_DEPENDENCY_PROBE_MANIFEST="$trial/candidate-manifest.json"
"$trial/verify/bin/python" -B -m pytest -q \
  evidence/agent-m03/nd-agent-02-c/test_dependency_probe.py \
  evidence/agent-m03/nd-agent-02-c/test_budget_mapping_probe.py
# rebuild 解释器执行同样的命令并留独立日志。
"$trial/verify/bin/python" -B ops/run_grouped_tests.py --skip-web
```

分组脚本注入仓库 API/worker 源码，不需要 editable 自由解析。日志分组记录实际 passed/skipped、pytest/ruff 版本，既有 opt-in skips 不增减；编译输出由 PYTHONPYCACHEPREFIX 隔离。旧回归通过不验收 Agent。若测试必须安装本项目，使用另经批准的构建工具/`--no-deps`，不得临时联网安装未锁 build dependencies。

## 3. 交付与签认门槛

提交原生 Linux 独立锁/manifest、与 Windows 的版本/marker/轮子差异、输入 commit/dirty 状态、两次离线重建与哈希负向、全部 probes/分组/static 的命令和结果。原始 wheelhouse/venv/report/log 留在 `.pi/`；证据摘要与可重跑材料版本化，不提交机器路径/凭证。

此外 M11 单独提供批准目标镜像 digest、系统库、运行/CI/worker 角色隔离与完整构建/回滚验证；M01 审核新闭包许可证/CVE/遥测/反序列化；M00/消费者/Owner 按签认清单确认。没有这些材料时 02-C 仍 review，02-D～H blocked，不能把本执行单标成 Linux passed。

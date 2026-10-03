# 02-C 离线许可证材料与 Ubuntu 验证阻断

- **日期 / 基线**：2026-10-03，main `8009841`，开场 clean。
- **状态**：审核输入已收集；许可证兼容性、CVE、遥测、来源/原生库审核与所有签认仍 pending。不是安全通过或正式锁。
- **责任**：M11 只读材料与复核，M03 候选锁；M01/Owner 后续审核。范围见 [变更记录](../../../progress/changes/20261003-M11-agent-supply-chain-evidence.md)。

## 1. Ubuntu 验证实际进展

执行 `docker pull docker.m.daocloud.io/library/ubuntu:24.04` 成功，本地镜像 digest 为 `sha256:a853f94d226358a79c740cfc7bce0c289748f3fe3488d921d038ccd752c61b60`，linux/amd64。只运行临时检查容器：`/etc/os-release` 报 Ubuntu 24.04.5 LTS，glibc 2.39，x86_64；没有启动 Compose/app/PG 或修改宿主系统。

Python 来源查阅 `actions/python-versions` 的 manifest commit `52ee1aa09f9f41a759b7a7010eda15fb0e2b190e`（blob `e7d778fdd533b48b1ed338da122e0996747a2ffd`）。对应构建为：

```text
https://github.com/actions/python-versions/releases/download/3.12.10-14343898437/python-3.12.10-linux-24.04-x64.tar.gz
```

GitHub release API 返回大小 **121612690 bytes**、`digest=null`。实际命令：

```bash
curl --fail --silent --show-error --location --retry 1 --max-time 240 \
  --output /tmp/py312/python-3.12.10-linux-24.04-x64.tar.gz \
  https://github.com/actions/python-versions/releases/download/3.12.10-14343898437/python-3.12.10-linux-24.04-x64.tar.gz
```

两次均 exit 28：首轮 240 秒/14355452 bytes，重试 240 秒/15500657 bytes；未解压、安装或执行不完整包。之前尝试的 Python standalone `20251014` 批次不含 3.12.10，猜测 Actions release tag 返回 404；raw manifest 下载也超时，之后 GitHub API blob 成功给出正确版本。这些失败没有通过换 Python 版本或绕过 hash 来修绿。

**Ubuntu CI 验证仍 blocked**：没有固定解释器安装、原生 resolver report、独立候选锁、双离线重建或回归。Ubuntu 镜像可拉取不代表 CI 或官方来源签认完成；本地容器不是 GitHub hosted runner。Arch 编译 Python 不替代 Ubuntu 构建，bookworm 锁不复制为 Ubuntu 锁。下一次需取得完整且经来源/完整性审核的固定 Python 构建，按 [原生执行单](linux-validation.md) 重新执行。

## 2. 离线材料

输出：[license-inventory.json](linux-bookworm/license-inventory.json)。SHA-256：`4ecdba8748c6762cc58f84893007e054037bd5c945e6b5daeb49d0d37efce8d0`。

输入为已版本化 bookworm candidate manifest 和已有忽略目录 wheelhouse。使用主项目 CPython 3.12.10 的 **stdlib** `hashlib/zipfile/email/json`，未导入 wheel 包或安装任何依赖。逐项验证原始 wheel SHA-256；唯一顶层 `.dist-info/METADATA` 的包名按 `[-_.]+` 规范化比较、版本精确比较；重复 ZIP member 或缺失 wheel 即停止。不解压。

记录 METADATA 原始摘要、License-Expression、旧 License 字段的前 240 字符/完整字段长度和摘要、License classifiers、声明 License-File 及实际随包许可证文件路径/长度/摘要。兼容 `.dist-info/licenses/` 和旧 `.dist-info/` 位置；同时检测 wheel 各目录以 LICENSE/LICENCE/COPYING/COPYRIGHT/NOTICE 命名的文件。该检测不是对所有内嵌二进制许可证的完整识别。

| 检查 | 结果 |
| --- | --- |
| wheel 哈希与 METADATA 身份 | 109/109 相符 |
| 有 License-Expression | 62 |
| 有旧 License 字段 | 45 |
| 有 License classifier | 45 |
| 检出随包许可证文本 | 107 |
| 未解析到声明的 License-File | 0 |
| 三种许可证声明均无 | 0 |
| 未检出随包许可证文本 | 2：grpcio-tools、langsmith |
| Windows 原候选记录为 unchanged_baseline 且同版本 | 61 |

许可证字段覆盖数重叠，不能相加当总数。61 项比较只继承 Windows manifest 的原基线标识，不证明 Linux wheel 字节、角色锁或供应链审批已通过。此 109 包闭包含旧 API/worker/测试包，不是最小 Agent runtime 锁或完整 SBOM。

## 3. 需要人工审核的事实

| 包 | wheel 中声明 / 材料限制 | 后续处理 |
| --- | --- | --- |
| PyMuPDF 1.26.7 | 旧 License 字段为 `Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License`；随包 COPYING；原基线版本未变 | Owner/法务确认项目采用的许可和分发/服务义务；这是已有解析依赖，不称为 Agent 新引入问题 |
| psycopg 3.3.6 / psycopg-binary 3.3.6 / psycopg-pool 3.3.3 | License-Expression 为 `LGPL-3.0-only`，随包 LICENSE.txt | 审核链接/分发义务和 binary 内嵌 libpq/OpenSSL 等原生库；顶层元数据不足以批准所有原生库 |
| langsmith 0.14.3 | 旧 License 字段 MIT；未检测到随包许可证文件 | 从受控上游补齐文本/归属证据；SDK 遥测/序列化审查另行进行，不能用 MIT 声明代替隐私审查 |
| grpcio-tools 1.84.0 | 有许可证声明，但未检测到随包许可证文本 | 补齐上游/生成代码/原生组件文本并核对角色范围；不自行新增许可豁免 |
| LangGraph/core/openai adapter 候选 | LangGraph 系列声明 MIT；core/openai adapter 旧 License 字段 MIT | 保留原文及归属、核对传递闭包和政策；不是许可证兼容性签认 |

没有检测到文本不证明违法；声明许可证也不证明合规。CVE 扫描 **未执行**，不报告零漏洞，不安装未锁扫描器或以旧版本印象代替漏洞数据库。Windows wheel、OS/解释器/构建工具、二进制内嵌库、许可证兼容性和角色隔离仍待独立审查。

## 4. 可重跑复核

以下命令只读 inventory/manifest/wheel，不执行包代码；本机必须保留原 wheelhouse。使用已存在的主项目解释器，不需新依赖。

```bash
cd /home/lumina888/Projects/Pivot
.venv/bin/python -B - <<'PY'
import hashlib
import json
import re
import zipfile
from email.parser import BytesParser
from pathlib import Path

base = Path('evidence/agent-m03/nd-agent-02-c')
report_path = base / 'linux-bookworm/license-inventory.json'
manifest_path = base / 'linux-bookworm/candidate-manifest.json'
windows_path = base / 'candidate-manifest.json'
wheels = Path('.pi/artifacts/nd-agent-02-c/linux-runtime-20261003-bookworm/wheels')
report = json.loads(report_path.read_text())
manifest = json.loads(manifest_path.read_text())
def sha(data):
    return hashlib.sha256(data).hexdigest()
def name(value):
    return re.sub(r'[-_.]+', '-', value).lower()
assert sha(report_path.read_bytes()) == '4ecdba8748c6762cc58f84893007e054037bd5c945e6b5daeb49d0d37efce8d0'
assert sha(manifest_path.read_bytes()) == report['candidate_manifest_sha256']
assert sha(windows_path.read_bytes()) == report['windows_manifest_sha256']
expected = {name(p['name']): p for p in manifest['packages']}
assert len(expected) == len(report['packages']) == 109
assert len({name(p['name']) for p in report['packages']}) == 109
for record in report['packages']:
    package = expected[name(record['name'])]
    assert record['version'] == package['version']
    assert record['wheel'] == package['wheel']
    path = wheels / record['wheel']
    assert sha(path.read_bytes()) == package['sha256'] == record['wheel_sha256']
    with zipfile.ZipFile(path) as archive:
        paths = [p for p in archive.namelist()
                 if p.count('/') == 1 and p.endswith('.dist-info/METADATA')]
        assert len(paths) == 1
        raw = archive.read(paths[0])
        assert sha(raw) == record['metadata_sha256']
        md = BytesParser().parsebytes(raw)
        assert name(md['Name']) == name(record['name'])
        assert md['Version'] == record['version']
        assert md.get_all('License-Expression', []) == record['license_expressions']
        assert md.get_all('License-File', []) == record['declared_license_files']
        legacy = md.get('License')
        assert (legacy[:240] if legacy is not None else None) == record['legacy_license_preview']
        assert (sha(legacy.encode()) if legacy is not None else None) == record['legacy_license_sha256']
        for item in record['packaged_license_files']:
            content = archive.read(item['path'])
            assert len(content) == item['size']
            assert sha(content) == item['sha256']
print('109 wheel/metadata/license records verified; approval remains pending')
PY
```

本轮另用 **bookworm 候选 verify venv** 在原 digest 容器中回跑 `test_dependency_probe.py` + `test_budget_mapping_probe.py`，显式指向 bookworm manifest、关闭 tracing/cache，`--basetemp` 位于新的忽略目录 `supply-chain-20261003-pytest`：**20 passed (7.36s)**。没有修改框架或预算映射。

收尾使用主项目 Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6，按已有 harness 注入 API/worker 源码，pytest 临时目录全部在新的忽略目录：

```bash
PYTHONPATH="$PWD/api/src:$PWD/worker/src" PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  tests/integration/db tests/contract --ignore=tests/contract/stream \
  --basetemp="$PWD/.pi/artifacts/nd-agent-02-c/supply-chain-20261003-contract-db"
# 331 passed (24.43s)
PYTHONPATH="$PWD/api/src:$PWD/worker/src" PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  tests/unit/qa tests/unit/runs tests/contract/stream \
  --basetemp="$PWD/.pi/artifacts/nd-agent-02-c/supply-chain-20261003-qa"
# 79 passed (1.01s)
.venv/bin/python -B -m ruff check --config api/pyproject.toml api/src worker/src \
  evidence/agent-m03/nd-agent-02-c/test_dependency_probe.py \
  evidence/agent-m03/nd-agent-02-c/test_budget_mapping_probe.py
# All checks passed!
```

文档内复核命令实际执行：**109 wheel/metadata/license records verified**。6 个本轮 Markdown、69 个本地链接、JSON 状态/计数/缺文本名单与内嵌 Python 语法检查通过。复核时纠正人工摘录的 grpcio-tools 版本为 manifest 实际 **1.84.0**，未改候选或生成清单。`git diff --check` 通过。主动 `lens_diagnostics(source=lsp, scope=paths)` 检查本轮 7 个 JSON/Markdown 文件：7 clean / 0 diagnostics（无 unavailable/inconclusive）。

未改业务、不重跑 Web/live/Compose/全量分组，上一轮 `895 passed / 1 failed / 19 skipped` 的本机 `.env` 存在性失败未修、配置未读删，不将本轮部分测试当全量绿。

## 5. 仍未关闭

02-C review、02-A/B/03-A/04-A 待消费者/Owner 签认；0 ready / 5 review / 24 blocked，02-D～H 不解锁。Ubuntu CI、正式角色锁/构建/回滚、许可证兼容性/CVE/遥测/原生库、批准 PG 环境继续 pending。DR-010/011、TBD-P0 与全部 GATE 不关闭。

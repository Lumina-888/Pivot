# 02-C 公开漏洞查询与许可证补充（待审核）

- **日期 / 基线**：2026-10-04，main `497c15c`，开场 clean。
- **状态 / 责任**：M11 诊断材料、M03 候选范围；安全/法律/Owner 签认仍 pending，不是正式锁、Agent 或 GATE 验收。
- **变更**：[范围记录](../../../progress/changes/20261004-M11-agent-public-supply-chain-check.md)。[机器可读报告](supply-chain-public-check.json)保留 OSV 请求/响应、对照查询、源码元数据和上游 LICENSE 全文/归属/版本材料。

## 1. 公开漏洞数据库

2026-10-04T02:36:09Z，使用已有 CPython3.12.10 stdlib urllib 向 `https://api.osv.dev/v1/querybatch` 提交109个公开 PyPI 包名及精确版本。请求逐项绑定 [Ubuntu manifest](linux-ubuntu/candidate-manifest.json)，原始摘要 `9616cf6ec12b4567bfdc700d7aafe8fda3a85a15425875555d65f9c035209c87`；其规范化包名/版本集合与 [bookworm](linux-bookworm/candidate-manifest.json)相同。

- 返回109个结果，均为空对象；本次数据库查询未返回候选版本 advisory 命中。
- 原始 HTTP 响应 SHA-256：`bca6412f8698a7d486be68bf82744eb008bc9ac4e2478111ece79ce138792b8d`。报告保留解析后的 JSON；复核不把重新序列化摘要当原始响应摘要。
- 正/负对照：requests2.32.3 命中 `GHSA-9hjg-9r4m-mvj7`；2.32.4 不命中该项。2.32.4 仍命中其他 advisory，所以只证明目标查询可区分其已知受影响/修复版本，不代表整个版本安全。
- 未安装 pip-audit/新扫描器，不下载或执行候选包。仅发送公开包名/版本；不发送项目文件、路径、配置或文档。

**无命中不等于零漏洞**：OSV 对未知包/版本也可返回空结果，不能据此证明覆盖。数据实时变化；此查询未覆盖 OS、Python、构建工具、原生内嵌库、Windows-only colorama/pywin32，也不判断运行暴露/可利用性。安全审核结论仍 pending。

## 2. 许可证来源

此前109个wheel中107个检出许可证文本，grpcio-tools/langsmith两项缺失。此次只补充审核输入，不修改wheel/锁/旧inventory或其摘要。

| 项目 | grpcio-tools 1.84.0 | langsmith 0.14.3 |
| --- | --- | --- |
| PyPI sdist bytes | 6401750 | 4967528 |
| sdist SHA-256 | `210ac5ac9803569490ec33574b7e995bc087815b00d9b777e0134cab5ed9a379` | `60c42b2c9e3e798ebbab3caa286ac25201b2b1861ed915dfe5851b076d6a9bc4` |
| PKG-INFO 主包声明 | Apache-2.0 | MIT |
| 上游标签 | grpc/grpc `v1.84.0` | langchain-ai/langsmith-sdk `v0.14.3` |
| 固定 commit | `3252a89f10d8e92997862167ca7d095ecda85973` | `5f425645bc1d50e02f87607062ed93aa99578cde` |
| 主 LICENSE blob | `98352651c8f9280b23bcedb750968b41421d925f` | `136a251bf3a98cd47ba4c4cf5d2517d37236eaa1` |

下载后先比对原始 SHA-256 与 PyPI，再通过 tarfile 只读成员/PKG-INFO；无解压、安装或 setup 执行。源码归档中的 utf8_range/scikit-learn/uuid-utils/zstandard 许可证属于第三方，不能替代主包 LICENSE。两项上游主 LICENSE 全文以固定 GitHub blob 保存，验证 Git `blob <length>\0<bytes>` 身份、长度和 SHA-256；版本文件经 ast.literal_eval 静态核对与候选相符。langsmith pyproject 使用 dynamic version，首次误按静态 project.version 读取产生 KeyError；随后按声明的 `langsmith/__init__.py` 读取 `__version__`，未猜测版本或执行模块。

langsmith 官方源码下载90秒后exit28，仅收到1119276/4967528 bytes；未使用该不完整文件。清华 HTTPS 完整下载与官方PyPI摘要一致后才采用。不改宿主源/默认pip配置。源码包/标签来源记录是审核输入，不代表签名链、标签真实性/构建归属完整验证、wheel分发补齐或许可证兼容性批准。PyMuPDF双许可、psycopg LGPL/原生组件、SDK遥测仍需人工审核。

## 3. 离线复核

以下命令仅使用版本化JSON/manifest，校验来源绑定、对照结果、许可证/版本文本摘要与Git blob身份，不调用网络、不执行上游代码：

```bash
cd /home/lumina888/Projects/Pivot
.venv/bin/python -B - <<'PY'
import ast
import hashlib
import json
import re
from pathlib import Path

base = Path('evidence/agent-m03/nd-agent-02-c')
r = json.loads((base / 'supply-chain-public-check.json').read_bytes())
def sha(data):
    return hashlib.sha256(data).hexdigest()
def packages(path):
    return {(re.sub(r'[-_.]+', '-', p['name']).lower(), p['version'])
            for p in json.loads(path.read_bytes())['packages']}
u = base / 'linux-ubuntu/candidate-manifest.json'
b = base / 'linux-bookworm/candidate-manifest.json'
assert r['status'] == 'diagnostic-only' and r['approval'] == 'pending'
assert sha(u.read_bytes()) == r['manifests']['ubuntu_sha256']
assert sha(b.read_bytes()) == r['manifests']['bookworm_sha256']
assert packages(u) == packages(b)
queries = r['osv_batch']['request']['queries']
results = r['osv_batch']['response']['results']
assert len(queries) == len(results) == 109
assert {(p['package']['name'], p['version']) for p in queries} == packages(u)
assert all(p['package']['ecosystem'] == 'PyPI' for p in queries)
assert all(p == {} for p in results)
controls = r['osv_control']['response']['results']
target = 'GHSA-9hjg-9r4m-mvj7'
assert target in {v['id'] for v in controls[0]['vulns']}
assert target not in {v['id'] for v in controls[1]['vulns']}
assert len(r['upstream_licenses']['packages']) == 2
for p in r['upstream_licenses']['packages']:
    for prefix in ('license', 'version'):
        raw = p[prefix + '_text'].encode()
        assert sha(raw) == p[prefix + '_sha256']
        blob = b'blob ' + str(len(raw)).encode() + b'\0' + raw
        assert hashlib.sha1(blob).hexdigest() == p[prefix + '_blob_sha1']
    assignments = [n for n in ast.parse(p['version_text']).body
                   if isinstance(n, ast.Assign) and any(
                       isinstance(t, ast.Name) and t.id == p['version_assignment']
                       for t in n.targets)]
    assert len(assignments) == 1
    assert ast.literal_eval(assignments[0].value) == p['version']
    assert (p['name'], p['version']) in packages(u)
assert not r['download_failure']['used']
print('109 queries, advisory controls, 2 upstream license/version records verified; pending')
PY
```

原始诊断产物位于 `.pi/artifacts/nd-agent-02-c/supply-chain-20261004/`：batch/control JSON、完整/不完整sdist、只读许可证检查与upstream记录；不提交二进制归档。报告由这些结构化产物生成，未修改候选/供应商或安装新依赖。

## 4. 验证与未完成项

上述离线复核命令实际执行通过：109 queries、advisory controls、2 upstream license/version records verified。报告 SHA-256：`da90df78a6c26e6d290c4fe38d8b362bf38c271f9c1ac9443bd45a7999d4a761`。

本机原项目环境 CPython3.12.10/pytest9.1.1/ruff0.16.6，执行：

```bash
.venv/bin/python -B ops/run_grouped_tests.py --skip-web
```

十组完整 Python 回归 **905 passed/19 skipped/0 failed**，harness exit0；ruff/compileall通过。Pipeline281 passed/18 skipped，保留两个既有Starlette/AnyIO弃用警告；原始日志为 `.pi/artifacts/nd-agent-02-c/supply-chain-20261004/grouped-tests.log`。这是本机回归，不是候选依赖环境或正式CI验收。另复核2个sdist原始hash及全部记录的第三方文本，7份本轮Markdown/112个本地链接有效，`git diff --check`通过；8个改动文件主动LSP检查8 clean/0 diagnostics，无unavailable/inconclusive。未运行正式Ubuntu CI、目标候选容器重建、项目镜像、Web/浏览器、PG/Saver/恢复或live模型。

02-C仍review；0 ready/5 review/24 blocked，消费者/Owner签认、正式CI/角色锁/构建来源、许可证兼容性/CVE/遥测/原生库审核仍pending。02-D～H、DR-010/011/TBD-P0与所有GATE不解锁。

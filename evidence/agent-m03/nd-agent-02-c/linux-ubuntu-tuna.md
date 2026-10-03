# 02-C Ubuntu 清华源诊断（非 CI 验收）

- **日期 / 基线**：2026-10-03，main `93c24fe`，开场 clean。
- **请求 / 范围**：Owner 请求换清华源；只在临时 Ubuntu 容器及忽略 artifact 目录中操作，见 [变更记录](../../../progress/changes/20261003-M11-ubuntu-tuna-validation.md)。
- **状态**：清华下载/源码构建/原生候选解析成功；没有完成 Actions 官方预编译构建或 hosted CI、双离线重建、Agent 验收、安全签认/正式锁。

## 1. 清华下载与完整性

```bash
curl --fail --silent --show-error --location --max-time 120 \
  --output Python-3.12.10.tar.xz \
  --write-out 'HTTP %{http_code}; bytes %{size_download}; seconds %{time_total}; speed %{speed_download}\n' \
  https://mirrors.tuna.tsinghua.edu.cn/python/3.12.10/Python-3.12.10.tar.xz
```

实际 **HTTP 200 / 20520960 bytes / 3.418463 秒 / 6003011 bytes/s**，SHA-256 为 `07ab697474595e06f06647417d3c7fa97ded07afc1a7e4454c5639919b46eaea`。先与之前本机源码摘要核对，随后取得官方 HTTPS `https://www.python.org/ftp/python/3.12.10/Python-3.12.10.tar.xz.sigstore`，base64 解码 `messageSignature.messageDigest.digest`（算法 `SHA2_256`）后与清华原始字节摘要比较，相符。

Sigstore bundle 原始 SHA-256 为 `8844be554fff683017ad0a9daffefdc1e7d4f67b13751d4004b84ed0398b096c`。**未做完整 Sigstore 签名/证书链/透明日志验证**；官方 HTTPS 摘要对照不代替完整供应链签认。官方源码本体直连下载60秒超时，仅取得240462 bytes；管道产生的局部摘要不是源文件摘要，不采用、不安装。上轮 Actions 预编译包下载阻断仍保留，不声称清华镜像了该 artifact。

## 2. 隔离 Ubuntu 构建

| 项 | 实测 |
| --- | --- |
| Ubuntu 基础镜像 digest | `sha256:a853f94d226358a79c740cfc7bce0c289748f3fe3488d921d038ccd752c61b60` |
| 镜像取得渠道 | 已有 `docker.m.daocloud.io/library/ubuntu` 镜像；本轮不变更 Docker daemon 代理/镜像源 |
| OS / glibc / 架构 | Ubuntu24.04.5 / glibc2.39 / x86_64 |
| Python | CPython3.12.10，容器内源码构建，GCC13.3.0；不是Arch解释器或Actions artifact |
| pip | 25.0.1，源码自带ensurepip；未升级 |
| SSL / SQLite | OpenSSL3.0.13 / SQLite3.45.1 |

临时容器内使用以下 deb822 源，宿主不变：

```text
Types: deb
URIs: https://mirrors.tuna.tsinghua.edu.cn/ubuntu/
Suites: noble noble-updates noble-backports noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
```

容器基础镜像没有 CA bundle，apt 初始通过 `Acquire::https::CaInfo=/run/pivot-ca.crt` 使用只读挂入的宿主 CA bundle，随后安装 ca-certificates。未关闭 TLS 或 apt signature 验证，未添加 trusted-host/allow-unauthenticated。runtime apt update 从清华取得 **33.2 MB / 9 秒**，无签名/证书绕过。系统包实际版本留在 artifact 的 `system-packages.tsv`；这是观察记录，**不是**固定构建/OS锁。

构建安装包：build-essential、ca-certificates、xz-utils、libssl-dev、zlib1g-dev、libbz2-dev、libreadline-dev、libsqlite3-dev、libffi-dev、liblzma-dev、libncurses-dev、uuid-dev。容器内源码执行：

```bash
./configure --prefix=/trial/python --with-ensurepip=install
make -j4
make install
```

首次 `docker run --rm ... build-python.sh` 超过600秒工具执行窗口，容器仍继续运行。随后日志和 `system-packages.tsv` 证明已到安装末段及后续步骤；原临时容器自行退出。没有因工具超时重跑构建或宣称该工具调用exit0。

新基础容器执行 Python 时发现缺 `libsqlite3.so.0`，这是基础镜像未带构建容器运行库，不是静默忽略导入。通过清华 apt 安装运行库（libsqlite3-0、libffi8、libreadline8t64、libbz2-1.0、liblzma5、libssl3t64、zlib1g、libuuid1、ca-certificates）后复核成功：

```text
3.12.10 (main, Oct 3 2026, 14:37:48) [GCC 13.3.0]
glibc ('glibc', '2.39') pip 25.0.1
ssl OpenSSL 3.0.13 30 Jan 2024 sqlite 3.45.1
stdlib imports and roundtrips passed
```

检查 sys.platform/x86_64/精确Python与pip版本，以及 ssl/sqlite3/ctypes/bz2/lzma/readline/uuid 导入、SQLite select1、bz2/lzma往返。新的验证容器 `pivot-ubuntu-tuna-20261003-verify` 最终 **exited / exit0 / running=false**。宿主Python、主.venv、API/Web服务与用户配置未变。

## 3. 清华 pip 原生解析

用上述 Ubuntu 解释器新建 resolver venv，仅从原 Windows manifest 提取roots和规范化版本约束；**没有复制 Windows 或 bookworm 的wheel哈希锁**。在Ubuntu原生环境执行：

```bash
/trial/resolver/bin/python -B -m pip --isolated --disable-pip-version-check --no-cache-dir install \
  --dry-run --ignore-installed --only-binary=:all: \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple --timeout 30 --retries 1 \
  -r /trial/roots.txt -c /trial/versions-only.txt \
  --report /trial/resolve-report-tuna.json
```

解析 **109个非yanked wheel**，报告sys_platform=linux、python_full_version=3.12.10；规范化包集合与bookworm候选相同，版本差 **0**，report里的原始wheel SHA-256差 **0**。这说明清华为本次候选提供相同wheel，不将bookworm锁冒名为Ubuntu锁。源报告摘要为 `6bae4afdce0896fbea8ba80e549313ff2254e8a4c690ab9a1264b1f68da928ab`。

这是 **dry-run候选诊断**，没有安装Agent依赖，没有生成/发布Ubuntu角色锁，没有双离线重建、哈希负向、20probes或分组回归。临时构建工具及解释器来源与Actions不同，源目录/日志不等于CI生产镜像验收；Ubuntu CI仍pending。

## 4. 本机复跑材料与检查

本轮目录 `.pi/artifacts/nd-agent-02-c/linux-ubuntu-tuna-20261003/` 包含原始源码/Sigstore bundle、独立源码构建/解释器、build-python.sh、verify-runtime.sh、ubuntu.sources、apt/configure/build/install/runtime日志、roots/versions-only、原生resolve-report与比较日志；全部忽略，不提交大文件或机器路径/企业资料。

源码构建脚本在固定Ubuntu镜像内运行，artifact目录挂`/trial`，ca bundle挂`/run/pivot-ca.crt`，临时源挂`/etc/apt/sources.list.d/ubuntu.sources`。验证脚本还把已版本化`evidence/agent-m03/nd-agent-02-c/`只读挂`/input`。重跑应使用新artifact目录和新容器名，不覆盖旧日志，也不直接在宿主运行apt/build脚本。

收尾：2个artifact脚本`bash -n`通过；6个本轮Markdown/72个本地链接/3个内嵌shell block语法检查通过，原生report摘要/HTTPS/平台/109计数复核通过；主动LSP检查6个Markdown为6 clean/0 diagnostics（无unavailable/inconclusive），`git diff --check`通过。验证容器再次确认exit0/running=false。

本轮版本化变更只有证据/进度文档；未重跑业务/Web/全量回归；上轮全量本地`.env`存在性失败未修、未读取/删除配置，不以环境成功代替测试通过。

## 5. 下一步边界

清华网络路径可用，Python源码/容器apt/pip临时诊断成功。后续可在单独批准切片中核对该源码构建是否可作为CI诊断工具链，再做独立Ubuntu锁、双离线重建/探针/回归；若仍要求Actions artifact，应取得官方完整包后另验，不能无说明替换。

源码签名/工具链供应链、许可证兼容性/CVE/遥测、角色锁/完整镜像构建、消费者/Owner签认仍pending。02-C继续review，0 ready/5 review/24 blocked；02-D～H、DR-010/011、TBD-P0及所有GATE不变。

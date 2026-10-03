# 本机 Linux 开发环境

> 2026-10-03，本机开发/测试配置，不是 staging、生产配置、Agent Contract 发布或 GATE 验收。
> 当前工作区：`/home/lumina888/Projects/Pivot`，分支 `main`。历史 Windows 路径不用于本机命令。
> 配置与实测见 [环境证据](../evidence/local-linux-20261003.md)。

## 1. 工具与下载源

- 系统 Python 3.14.7 保持不变。独立 CPython 3.12.10 位于 `~/.local/share/pivot/python/3.12.10/`，入口 `~/.local/bin/python3.12`；项目环境 `.venv/`。
- Node 26.8.2 / npm 11.19.1 沿用本机已有 mise 安装，与历史开发证据版本一致；不是 CI Node 20 目标平台验证。
- Git 仅在该仓库设置 `user.name=lumina888`（实际登录用户名），沿用已有全局邮箱；没有修改全局身份。
- 用户级 pip 配置 `~/.config/pip/pip.conf`：`https://pypi.tuna.tsinghua.edu.cn/simple`。使用 HTTPS，不添加 trusted-host 或额外索引。
- Arch `/etc/pacman.d/mirrorlist` 首选 `https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch`；保留原阿里云/腾讯/中科大作为备用，原列表有备份。不修改 Omarchy/OmarchyCN 独立仓库。
- Python 源码来自清华 Python 镜像。npm 仍使用官方 `https://registry.npmjs.org/`；Playwright 浏览器来自官方 CDN。清华没有提供相应公共服务，不伪称所有渠道都已切换。

```bash
cd /home/lumina888/Projects/Pivot
source .venv/bin/activate
python --version
python -m pip config get global.index-url
python -m pip check
```

现有 API 的 test/lint/http/postgres/minio/qdrant/redis/playwright extras、worker 的 celery/parse extras 和公共契约依赖已安装。`web/node_modules` 按既有 package-lock 安装。未改 pyproject、正式锁、框架版本、CI 或业务源码；主环境没有 LangGraph。

## 2. 开发服务

本机已创建用户级 `pivot-api.service`、`pivot-web.service`，未设为开机自动启动：

```bash
systemctl --user start pivot-api.service pivot-web.service
systemctl --user status pivot-api.service pivot-web.service --no-pager
systemctl --user stop pivot-web.service pivot-api.service
journalctl --user -u pivot-api.service -u pivot-web.service -n 80 --no-pager
```

- Web：`http://127.0.0.1:3000/login`。
- API：`http://127.0.0.1:8000`，`/healthz` 返回 200。
- 登录用户 `local-admin`，随机口令在仓库根 `.env` 的 `PIVOT_BOOTSTRAP_PASSWORD`；文件权限 600，已忽略，不提交。不要将整个文件复制进日志或聊天。
- `web/.env.local` 注入本机 API origin 并关闭 Next 遥测；API 配置也关闭 LangChain/LangSmith tracing。
- 使用 memory 存储、native 解析、同步 ingest、hash embedding 和 local Writer。没有真实供应商、企业文档、密钥或生产阈值。
- memory 数据在 API 重启后消失；当前已放入低敏测试 PDF。现有 memory composition root 未连接检索索引，因此搜索为空、无证据问答 refused。真实检索需另配置 Qdrant 等存储，不通过修改门禁弥补。
- `/readyz` 当前真实返回 503/not_ready，四个真实依赖均 false；不等同 `/healthz` 或开发测试失败。
- 导出公开地址仅用既有 `https://files.pivot.test` 测试占位，不是可下载服务。现有 signer 拒绝 localhost，因此不得改成 loopback 地址或绕过校验。
- 参数只属于该低敏本地 fixture，不是生产默认或 TBD-P0 冻结。两个服务仅监听 loopback。

## 3. 验证命令

```bash
cd /home/lumina888/Projects/Pivot
.venv/bin/python ops/run_grouped_tests.py --skip-web
npm --prefix web ci --no-audit --no-fund
npm --prefix web test
(cd web && node_modules/.bin/tsx ../tests/e2e/user/test_user_web.mjs)
(cd web && node_modules/.bin/tsx ../tests/e2e/admin/test_admin_web.mjs)
npm --prefix web run typecheck
NEXT_TELEMETRY_DISABLED=1 npm --prefix web run lint
```

本轮 Python 661 passed / 19 skipped，ruff/compileall passed；Web 18/13/8 passed，typecheck/lint passed。浏览器安装完成（Playwright 1.63.0、Chromium v1243，Arch 使用官方 Ubuntu fallback），真实浏览器登录/十页组 11 passed。

浏览器测试自行启动临时 Next；不要让两个 Next 进程同时写同一 `.next`：

```bash
systemctl --user stop pivot-web.service
NEXT_TELEMETRY_DISABLED=1 .venv/bin/python ops/run_playwright_login.py
systemctl --user start pivot-web.service
```

## 4. Docker 与未完成项

Docker daemon 已启用；用户已加入 docker 组（等同 root 级容器权限）。已有会话需重新登录或运行 `newgrp docker`。验证过 Docker client/server 29.7.2 和 Compose 5.5.1，尚未拉起四个依赖容器。

官方 Docker Hub 直连超时；本机已有 Clash 的 `http://127.0.0.1:7897` 可连官方 registry。添加 daemon proxy 的两次 pkexec 授权均超时，**没有写入代理配置**。项目私有 artifact 中保留准备好的配置和授权脚本，先检查再执行：

```bash
cd /home/lumina888/Projects/Pivot
pkexec /usr/bin/bash "$PWD/.pi/artifacts/local-linux-20261003/configure-docker-proxy.sh"
newgrp docker
```

该脚本仅新增 `/etc/systemd/system/docker.service.d/pivot-proxy.conf`、重载并重启 Docker，不修改现有 daemon.json；新镜像下载依赖 Clash 保持运行。不使用未知 Docker 镜像站。

授权完成后，可用已有 Compose fixture 验证拉取与启动；这不会自动把当前宿主 API 的 memory 配置切换为真实存储：

```bash
docker compose --env-file ops/compose.env.example pull postgres minio qdrant redis
docker compose --env-file ops/compose.env.example up -d postgres minio qdrant redis
docker compose --env-file ops/compose.env.example ps
```

上述 example 使用明确的开发占位凭证，只能在 loopback fixture 使用；实际持久化联调应创建私有配置、替换凭证、运行迁移并确认四个探针，不运行 app profile 或连接 ECS/真实供应商。CI 仍不得 build/up Compose。

当前 Arch 主机的开发回归不替代 02-C 要求的 Debian runtime/Ubuntu CI 原生候选锁、双离线重建、供应链与镜像审核。02-A/B/C 仍 review，业务实现与所有 GATE 状态不变。

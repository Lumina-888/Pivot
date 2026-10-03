# 2026-10-03 本机 Linux 开发环境与清华默认源

- **状态**：用户授权的本机配置已执行，真实 Docker 存储联调部分 blocked（代理配置等待系统授权）。不是 Agent Contract 发布或完成审批。
- **授权来源**：用户要求“将这台电脑配置到项目可用”，追加“将默认下载渠道配置为清华源”。不扩大为生产部署、真实供应商调用或代签消费者。
- **Accountable / Contributors**：M11 环境/服务/验证，M03 Python 环境记录，M00 恢复入口同步。
- **原基线**：main `8782c7c`，SPEC-1.1 / AGENT-SPEC-1.0 / MODULE-SPEC-1.2 / contract-v0.1；契约版本不变。

## 范围与兼容

1. 安装独立 Python 3.12.10 与项目 `.venv`，不替换系统 3.14.7；安装现有 extras，Web 按原 lock 安装，Node/npm 版本不变。
2. pip 默认源设为清华 HTTPS，Arch 首选清华并备份/保留原源；不改 Omarchy 仓库，不虚构 npm/Docker/Playwright 的清华镜像。
3. 经 pkexec 启用现有 Docker，增加用户 docker 组；明确其 root 等价权限和会话刷新条件。daemon proxy 两次授权超时，尚未修改；不绕过认证。
4. 新建私有、仅 loopback 的用户级 API/Web 服务配置与低敏本地 fixture。现有 API 路由、状态、错误与预算政策不变；没有正式恢复/生产下载能力。
5. `AGENTS.md`、根进度和交接入口标明当前 Linux 路径与环境证据，历史 Windows 证据保留。新增 `ops/runbook-local-linux.md` 与 `evidence/local-linux-20261003.md`。

## 验证与边界

现有十组 Python 661 passed / 19 skipped，ruff/compileall 通过；Web 18/13/8 passed，typecheck/lint 通过；opt-in 浏览器组 11 passed。启动 smoke 验证 health、登录、native PDF 解析与无证据拒答/SSE。memory 模式未连索引，搜索为空、readyz 为 503；Docker 镜像拉取被网络阻断，待系统代理授权。

完整命令、初轮失败及未执行项见 [环境证据](../../evidence/local-linux-20261003.md)。当前主机不是批准的 Debian runtime/Ubuntu CI 原生依赖锁验收环境，不安装未签认 Agent roots；02-A/B/C、DR-010/011、全部 GATE 保持原状态。

## 回滚与保密

本机可停止两个用户服务；不删除用户文档或 Docker volumes。Arch 原镜像列表有时间戳备份，Python 独立目录与 `.venv` 不影响系统解释器；pip 变更仅在用户配置。密码/Token secret、服务文件及源构建日志不提交，复用说明不包含凭证。Docker 组和 daemon enable 属系统级变化，回滚须 Owner 经授权处理，不能静默撤销。

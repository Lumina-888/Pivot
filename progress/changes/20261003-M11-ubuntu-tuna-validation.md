# ND-AGENT-02-C 清华源与 Ubuntu 源码构建诊断

- **日期 / 基线**：2026-10-03，main `93c24fe`；开场 clean。
- **授权范围**：Owner 当前请求“试试换清华源”；临时 Ubuntu 容器内使用清华 Python 源码/apt/pip HTTPS 源，不修改宿主系统或默认配置。
- **状态**：诊断成功，不是正式工具链/依赖发布、安全签认或 GitHub hosted CI 通过。
- **Accountable / Contributors**：M11 镜像/环境验证与证据；M03 记录候选解析边界；主线更新 PROGRESS/HANDOFF。M01/Owner 的供应链审核仍 pending。
- **依据**：[原生执行单](../../evidence/agent-m03/nd-agent-02-c/linux-validation.md)、[上轮阻断](../../evidence/agent-m03/nd-agent-02-c/supply-chain.md)。

## 方法与结果

清华没有本轮已确认的 Actions Python 预编译 artifact，使用清华 Python 3.12.10 官方源码镜像，在固定 Ubuntu 24.04 digest 容器中编译；不是复用 Arch 解释器或 Debian wheel 锁。源码 SHA-256 与官方 HTTPS Sigstore bundle 的 SHA2_256 messageDigest 相符；未做完整签名链/透明日志验证。

apt 保留 Ubuntu archive keyring/Signed-By、TLS 验证与包签名，未使用 trusted-host/allow-unauthenticated。仅临时容器内配置清华 noble/noble-updates/noble-backports/noble-security，系统包版本日志保留，不称为已冻结构建工具锁。

Ubuntu 原生 Python 3.12.10/pip25.0.1、stdlib 导入/往返检查通过；清华 pip 对原候选版本约束独立 dry-run 解析109个wheel，与bookworm候选包集合/版本/哈希差异均0；没有安装Agent依赖或生成发布锁。两次离线重建/技术探针/分组/Hosted CI仍未执行。

## 不变项

无业务源码、公开Contract、pyproject/正式锁、迁移、CI/Dockerfile/Compose或生产默认变更，不读删用户.env，不升级主.venv，不设置宿主apt/pip全局源。不调用模型/PG/ECS，不声明许可证/CVE或GATE通过。

02-C review、0 ready / 5 review / 24 blocked不变；02-D～H不解锁。无状态/权限/模型/检索语义变化，无新ADR；DR-010/011、TBD-P0继续开放。完整成功/失败限制和复跑材料见 [Ubuntu清华源证据](../../evidence/agent-m03/nd-agent-02-c/linux-ubuntu-tuna.md)。

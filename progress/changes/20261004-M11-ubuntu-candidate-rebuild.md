# ND-AGENT-02-C Ubuntu 候选锁与双离线重建

- **日期 / 基线**：2026-10-04，main `3460a2f`，开场 clean。
- **请求 / 范围**：Owner 请求根据 Pivot 进度继续开发；承接 02-C 下一步目标平台锁验证，在新临时 Ubuntu 容器/忽略目录完成源码工具链诊断候选，不实施 DoR 未满足的业务票。
- **状态**：技术验证材料已提交，依赖提案仍 proposed/review；不代签源码工具链、正式 CI、供应链或消费者/Owner 审批。
- **Accountable / Contributors**：M03 候选锁/manifest；M11 隔离环境/探针/回归/证据；根 PROGRESS/HANDOFF 同步。M01/Owner 审核仍 pending。
- **依据**：[依赖申请](20261002-M03-agent-dependencies-lock.md)、[原生执行单](../../evidence/agent-m03/nd-agent-02-c/linux-validation.md)、[上轮 Ubuntu 诊断](../../evidence/agent-m03/nd-agent-02-c/linux-ubuntu-tuna.md)。

## 方法与结果

固定 Ubuntu 24.04 digest，复用上轮只读 CPython3.12.10 源码构建产物；新 resolver 以版本约束原生解析清华 HTTPS PyPI，生成独立 109 wheel 哈希锁。不是复制 bookworm 锁；bookworm wheel 缓存仅在按本轮 report 逐字节 SHA-256 核验后离线复用。manifest 明确源码工具链与非 hosted CI 范围。

两个全新 venv 离线 hashes 安装、pip check 通过；xxhash 错误哈希 dry-run exit1/hash mismatch；技术探针各20 passed。完整 Python 分组895 passed/1 failed/19 skipped，ruff/compileall通过；唯一失败仍是根 `.env` 存在性断言与本机 gitignored 配置冲突，不读取/删除配置、不改测试修绿。600秒工具等待超时后检查容器，最终 docker wait/inspect exit1/已停止，未重跑安装冒充成功。详情见 [证据](../../evidence/agent-m03/nd-agent-02-c/linux-ubuntu.md)。

## 不变项与下一步

不改业务源码、公开契约、pyproject/正式锁、CI/Dockerfile/Compose、迁移、主 `.venv`、宿主源或用户配置。不访问真实模型/PG/ECS，无模型/权限/状态机/检索变化，不新增 ADR，不冻结 TBD-P0。

源码工具链不冒充 Actions artifact/hosted CI；正式 Ubuntu CI、角色锁/构建工具/系统库、完整签名链、许可证/CVE/遥测与消费者/Owner 签认仍 pending。02-C review，0 ready/5 review/24 blocked；02-D～H、DR-010/011 与所有 GATE 不变。全部依赖/预算 Contract 准入满足后才进入真实业务图实现。

# ND-AGENT-02-C 离线供应链材料补齐

- **日期 / 基线**：2026-10-03，main `8009841`；开场 clean。
- **状态**：技术材料收集，不是依赖发布、消费者签认或安全审批。
- **Accountable / Contributors**：M11 证据归档；M03 候选锁与进度，M01 后续许可证/CVE 审核，主线同步根进度与交接。
- **依据**：[02-C 依赖申请](20261002-M03-agent-dependencies-lock.md) §5/§7、[Linux 执行单](../../evidence/agent-m03/nd-agent-02-c/linux-validation.md) §3。

## 范围

1. 保留本轮 Ubuntu 24.04 容器检查与固定 Python 构建下载失败事实。不使用 Arch Python、Debian 锁复制或不完整下载冒充 Ubuntu CI 通过。
2. 对已有 bookworm wheelhouse 的 109 个候选 wheel 做只读 SHA-256 与 METADATA 包名/版本核对，提取许可证声明和随包许可证文件摘要，生成独立审核输入。
3. 归档可重跑命令、覆盖范围与限制；更新 M03/M11、PROGRESS/HANDOFF。

## 不变项

不修改业务源码、公开 Contract、pyproject、正式锁、迁移、CI、Dockerfile/Compose、生产默认或用户配置。不安装新依赖，不执行 wheel 中代码，不调用模型、PG、ECS、漏洞服务。不判断许可证兼容性，不以清单替代完整法律/安全审核；CVE、遥测、原生库和 artifact 来源签认仍 pending。

## 验证与兼容

材料文件不被运行时、默认测试或 CI 消费。使用 stdlib hashlib/zipfile/email/json，只解析已校验 wheel，且不解压。实际包名规范化后必须与 manifest 相符，版本必须完全相同；候选 wheel 缺失、重复 METADATA 或哈希不匹配即停止。

不改变状态机/权限/模型或检索配置，无新增 ADR；DR-010/011、TBD-P0、所有 GATE 和 0 ready / 5 review / 24 blocked 不变。作者不是审核批准人。证据见 [供应链材料](../../evidence/agent-m03/nd-agent-02-c/supply-chain.md)。

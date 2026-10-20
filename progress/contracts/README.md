# 已发布内部契约

本目录存放已经签认并正式发布的内部契约。这些契约不属于 `spec/contracts/` 的公开机器契约。公开基线是 contract-v0.2。本目录只约束内部模块接口和实现。

## 发布状态

### 内部契约

| 契约 ID | 版本 | 发布日期 | 状态 | 适用范围 |
|---|---|---|---|---|
| AGENT-INTERNAL | 0.1.0 | 2026-10-12 | released | 模型、工具、State 和 EvidenceRegistry |
| AGENT-BUDGET | 0.1.0 | 2026-10-12 | released | DR-010 预算策略和累计用量 |
| AGENT-DEPENDENCIES | 0.1.0 | 2026-10-12 | released | Python 3.12 的框架依赖锁定 |

### 恢复与持久化

| 契约 ID | 版本 | 发布日期 | 状态 | 适用范围 |
|---|---|---|---|---|
| AGENT-RESUME | 0.2.0 | 2026-10-12 | released | 澄清恢复公开 API，即 contract-v0.2 |
| AGENT-PERSISTENCE | 0.1.0 | 2026-10-12 | released | checkpoint、租约、事实和 outbox |

当前没有待发布契约。

## 发布纪律

1. 消费者签认并且 Owner 批准之后，契约进入 released。
2. 首次发布从 `draft.N` 升为 0.1.0。
3. 破坏性变更提升 major。兼容增强提升 minor。
4. 每份契约关联签认记录、输入 commit 和技术验证证据。
5. 契约发布后，依赖它的实现票才可以从 blocked 改为 ready。生产数值未关闭时，仍不批准运行。

## 契约文件

- `AGENT-INTERNAL-0.1.0.md` 定义模型、工具、State 和 EvidenceRegistry。
- `AGENT-BUDGET-0.1.0.md` 定义 DR-010 的预算策略和累计用量。
- `AGENT-DEPENDENCIES-0.1.0.md` 锁定 Python 3.12 的框架依赖。
- `AGENT-RESUME-0.2.0.md` 和 `AGENT-PERSISTENCE-0.1.0.md` 是恢复与持久化契约。

## 参考

- 签认记录在 `progress/approvals/`。
- 提案历史在 `progress/changes/`。
- 技术证据在 `evidence/agent-m03/` 和 `evidence/agent-m05/`。
- 早期审批入口是 `evidence/agent-m03/nd-agent-02-abc-review.md`。它是历史记录，不是当前待签清单。

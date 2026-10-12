# progress/contracts/ — 已发布内部契约

本目录存放已完成签认并正式发布的内部契约。这些契约不属于 `spec/contracts/` 的 contract-v0.1 公开机器契约，仅适用于内部模块间接口定义和实现约束。

## 发布状态

### Agent 内部契约（已发布）

| 契约 ID | 版本 | 发布日期 | 状态 | 适用范围 |
|---|---|---|---|---|
| AGENT-INTERNAL | 0.1.0 | 2026-10-12 | released | 模型、工具、State、EvidenceRegistry 内部接口 |
| AGENT-BUDGET | 0.1.0 | 2026-10-12 | released | DR-010 预算策略与累计用量 |
| AGENT-DEPENDENCIES | 0.1.0 | 2026-10-12 | released | Python 3.12 框架依赖锁定 |

### Agent 公开契约（已发布）

| 契约 ID | 版本 | 发布日期 | 状态 | 适用范围 |
|---|---|---|---|---|
| AGENT-RESUME | 0.2.0 | 2026-10-12 | released | Agent 澄清恢复公开 API (contract-v0.2) |
| AGENT-PERSISTENCE | 0.1.0 | 2026-10-12 | released | Agent checkpoint/租约/事实/outbox 内部契约 |

### 待发布契约（review 状态）

| 契约 ID | 版本 | 提案状态 | 工单 |
|---|---|---|---|
| (无) | - | - | - |

## 发布纪律

1. **签认要求**：消费者签认 + Owner 批准 → 进入 released 状态
2. **版本规则**：draft.N → 正式版本 0.1.0（首次发布）
3. **变更管理**：破坏性变更提升 major；兼容增强提升 minor
4. **追溯性**：每份契约关联签认记录、输入 commit、技术验证证据
5. **实现解锁**：契约发布后，依赖该契约的业务实现票可从 blocked → ready

## 契约文件

- `AGENT-INTERNAL-0.1.0.md` — 模型、工具、State 与 EvidenceRegistry 内部契约
- `AGENT-BUDGET-0.1.0.md` — DR-010 预算策略与累计用量契约
- `AGENT-DEPENDENCIES-0.1.0.md` — Python 3.12 框架依赖锁定

## 参考

- 签认记录：`progress/approvals/`
- 提案历史：`progress/changes/`
- 技术证据：`evidence/agent-m03/`, `evidence/agent-m05/`
- 审批入口：`evidence/agent-m03/nd-agent-02-abc-review.md`

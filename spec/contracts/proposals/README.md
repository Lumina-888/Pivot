# 未发布 Contract 提案

本目录只保存 proposed 机器可读草案，不属于 `contract-v0.1` 发布基线，不得生成生产客户端、挂载业务路由或用作 Owner 签认。已发布契约仍以 [上级 README](../README.md) 和 [openapi.yaml](../openapi.yaml) 为准。

| 草案 | 说明 / 审核入口 |
|---|---|
| [agent-resume.schema.json](agent-resume.schema.json) | AGENT-RESUME-0.1-draft.1；[ND-AGENT-03-A 提案](../../../progress/changes/20261003-M00-agent-resume-contract.md)，review 待签认 |
| [agent-persistence.schema.json](agent-persistence.schema.json) | AGENT-PERSISTENCE-0.1-draft.1；[ND-AGENT-04-A 提案](../../../progress/changes/20261003-M03-agent-persistence-contract.md)，review 待签认；内部元数据，不是 State/SQL DDL |

schema 使用 JSON Schema Draft 2020-12；恢复草案根默认校验 `ResumeRequest`。校验其他组件时，以整个文件为解析根，把根 `$ref` 替换为 `#/$defs/ResumeAccepted`、`#/$defs/Clarification` 或 `#/$defs/ResumeFailure`。不能只摘出组件后丢弃 `$defs`，也不能只校验 ResumeError 形状就声称验证了 status/code/retryable 的配对。

ResumeFailure 是测试用 `{http_status, body}` 包装；真实 HTTP 错误 body 仍为 SPEC 的统一信封，不携带 http_status。schema 检查只证明字段/类型/映射，不证明 owner、幂等、状态、取消、预算或实际 interrupt 恢复。

运行检查：

```bash
.venv/bin/python -B -m pytest tests/contract/test_contract_agent_resume_proposal.py -q -p no:cacheprovider
```

持久化草案根默认 LeaseToken；其他组件替换根 `$ref` 为 `#/$defs/CheckpointBinding`、`#/$defs/ResultCommitReceipt`、`#/$defs/OutboxRecord`、`#/$defs/ProviderAttempt` 或 `#/$defs/GovernancePolicy`，保持整个解析根。日期须启用 format checker；当前基线没有可选 RFC3339 checker，测试用 stdlib datetime 校验日历合法性，并结合 schema 的 UTC Z/T 格式。只校验正则不能证明日期有效。租约时间/版本相等、跨对象归属、序号唯一及 State 白名单须运行时验证。

```bash
.venv/bin/python -B -m pytest tests/contract/test_contract_agent_persistence_proposal.py -q -p no:cacheprovider
```

GovernancePolicy 不提供生产默认，测试数值只适用于 unit_fake_only。敏感字段检查仅覆盖本 schema 元数据边界，不验证真实 checkpoint 内容或已批准加密策略；未知用量必须保持 unreconciled/null 并在账本保留 reservation，不能以 null 当零成本。

发布需按提案消费者清单签认和 Contract/ADR 流程提升版本；未经审核不更新公开 OpenAPI/SSE/Worker/version/CHANGELOG。批准发布后再决定草案归档/升级，不让目录位置暗示已经可调用。

# 未发布 Contract 提案

本目录只保存 proposed 机器可读草案，不属于 `contract-v0.1` 发布基线，不得生成生产客户端、挂载业务路由或用作 Owner 签认。已发布契约仍以 [上级 README](../README.md) 和 [openapi.yaml](../openapi.yaml) 为准。

| 草案 | 说明 / 审核入口 |
|---|---|
| [agent-resume.schema.json](agent-resume.schema.json) | AGENT-RESUME-0.1-draft.1；[ND-AGENT-03-A 提案](../../../progress/changes/20261003-M00-agent-resume-contract.md)，review 待签认 |

schema 使用 JSON Schema Draft 2020-12；根默认校验 `ResumeRequest`。校验其他组件时，以整个文件为解析根，把根 `$ref` 替换为 `#/$defs/ResumeAccepted`、`#/$defs/Clarification` 或 `#/$defs/ResumeFailure`。不能只摘出组件后丢弃 `$defs`，也不能只校验 ResumeError 形状就声称验证了 status/code/retryable 的配对。

ResumeFailure 是测试用 `{http_status, body}` 包装；真实 HTTP 错误 body 仍为 SPEC 的统一信封，不携带 http_status。schema 检查只证明字段/类型/映射，不证明 owner、幂等、状态、取消、预算或实际 interrupt 恢复。

运行检查：

```bash
.venv/bin/python -B -m pytest tests/contract/test_contract_agent_resume_proposal.py -q -p no:cacheprovider
```

发布需按提案消费者清单签认和 Contract/ADR 流程提升版本；未经审核不更新公开 OpenAPI/SSE/Worker/version/CHANGELOG。批准发布后再决定草案归档/升级，不让目录位置暗示已经可调用。

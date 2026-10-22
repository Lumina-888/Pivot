# ND-AGENT-05 S2 补行：05-B 备用模型（小米 MiMo）live 冒烟

- 日期：2026-10-22
- 模型：小米 MiMo `mimo-v2.6-flash`（官方接口 `api.xiaomimimo.com`，密钥经 `api-key` 自定义请求头传递，凭证走安全录入不落仓库）
- 范围：补行 PR #17 未覆盖的备用模型冒烟。三步与主模型冒烟同口径：普通聊天、强制 `search_knowledge`、回喂检索结果后续调。

## 结果

| 步骤 | 期望 | 实际 | 用量 |
| --- | --- | --- | --- |
| 普通聊天 | 正常文本回复 | 一句话自我介绍正常返回 | 54 token |
| 强制工具调用 | 按 `tool_choice` 调用 `search_knowledge` | `finish_reason=tool_calls`，参数 query 为“员工年假天数” | 227 token |
| 回喂续调 | 读到片段证据后续调 `read_evidence` | 调用 `read_evidence`，参数 evidence_id 为回喂的 `ev-001` | 315 token |

三步合计 596 token。

## 与主模型的差异

- 主模型 DeepSeek 官方在 thinking 开启时拒绝强制 `tool_choice`（HTTP 400），强制调用须关闭 thinking。本次 MiMo 在思考开启下直接接受强制 `tool_choice`，未见同类限制。
- MiMo 响应带 `reasoning_content` 与 `reasoning_tokens` 计量，适配器侧解析与主模型同为 OpenAI 兼容形状，无额外处理。

## 结论

05-B 备用模型冒烟通过，05-B 工单可关单。ND-AGENT-05 剩余项仅 05-D 的业务复核集重跑与阈值判定（待 Owner 侧输入）。

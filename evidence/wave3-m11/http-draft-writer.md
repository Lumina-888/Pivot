# Wave 3 M05 HTTP Draft Writer 限制

环境：`PIVOT_LLM=http` 时 `assemble_runtime` 装配注入 endpoint/model/api_key/timeout 的 OpenAI 兼容 chat Writer；鉴权头可注入；主失败（超时/429/5xx）才切 `PIVOT_LLM_FALLBACK_*`。CI 用 `ScriptedJsonHttpClient`，无真实供应商、无密钥入库。不启动 Compose/uvicorn。

- 默认 `PIVOT_LLM=local` 仍为证据拼接，不外发。
- HTTP Writer 不写死供应商 URL、模型名或超时；这些仍为 `TBD-P0`。
- Citation 只从检索候选生成；`external_llm_allowed=false` 不得 HTTP。
- Fake HTTP 闭环 ≠ 生产 Writer / Verifier 盲评。
- Compose 仅 api 注入 `PIVOT_LLM*`；example 占位 `local`，不是冻结的 `TBD-P0`。worker 不写作。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-004 | unverified | HTTP Writer + Fake transport，不是 live DeepSeek/小米闭环；Verifier 仍为候选 ID 校验；无盲评、无企业 Golden Set |
| GATE-P0-001 | unverified | staging 允许低敏文档注入外部 LLM，不把 `DR-001` 审批标通过 |

`implemented`（可注入 HTTP Writer）≠ `verified`。

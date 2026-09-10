# 变更申请：dev-staging 供应商注入清单（不入库、不冻 TBD-P0）

- **日期**：2026-09-10
- **申请人**：Owner 确认选型 + 主线会话记录
- **背景**：`20260910-M00-dev-staging-scope.md` 已批准开发调试环境。Owner 给定 Embedding / Rerank / LLM / MinerU 选型。本文件只记录**注入用的 model id 与适配形状**，禁止写入业务代码默认值，禁止提交密钥与供应商 URL 到 git。
- **Owner 选型**（仅 `dev-staging` env，不是生产冻结）：

  | 用途 | 供应商 | Owner 给出的 model id | 适配现状 |
  |---|---|---|---|
  | Embedding | 硅基流动 | `BAAI/bge-m3` | 已有 `HttpQueryEmbedder`：OpenAI `{model,input}` + `data[].embedding`，与硅基 `/v1/embeddings` 同形 |
  | Rerank | 硅基流动 | `BAAI/bge-reranker-v2-m3` | 已有 `HttpBgeReranker`：`{model,query,documents}` + `results[].index`/`relevance_score`，与硅基 `/v1/rerank` 同形 |
  | Agent 主模型 | Owner 指定 | `deepseek-flash` | **无** Writer；需 ND-STG-02。控制台真实 id 可能是带前缀的字符串（如 `deepseek-ai/...`），以硅基模型列表为准注入 |
  | Agent 备用 | 小米 | `mimo-v2.5` | **无** Writer；小米文档常见 OpenAI 兼容 + 可能非 Bearer 的 `api-key` 头；未证实在硅基目录。主/备切换只注入，不写死 |
  | 解析 | MinerU 官方云 | （任务 API，无 embedding 式 model 字段） | **无** 解析器；ND-STG-03。公开文档为 `mineru.net` Bearer JWT、多为异步任务 |

- **注入约定**（实现时，不在本文件写 URL）：
  - `PIVOT_EMBEDDING=http` + endpoint/model/api_key；维数只来自 `PIVOT_QDRANT_VECTOR_SIZE`（bge-m3 常见 1024，**不冻进 SPEC/代码**）；
  - `PIVOT_RERANK=bge` + endpoint/model/api_key；阈值/top-k 不冻；
  - Writer：`PIVOT_LLM_ENDPOINT` / `PIVOT_LLM_MODEL` / `PIVOT_LLM_API_KEY`，备用 `PIVOT_LLM_FALLBACK_*`；主失败（超时/429/5xx）才切备用；Citation 仍必须在检索候选内；`external_llm_allowed=false` 不得外发；
  - MinerU：`PIVOT_PARSER=mineru` + 注入云 API token/endpoint；CI 默认启发式/stdlib。
- **不做**：不把上述 model id 写进源码默认值；不改 `ops/compose.env.example` 为真实供应商 URL；不标 GATE verified；服务器 OS 等部署时再与 Owner 确认。
- **影响模块**：M00 记录；实现分属 ND-STG-01~03、ND-W3-01。
- **是否触发 ADR**：否（staging 注入清单，不冻生产模型/维数；企业化仍走 `DR-001/007`）。
- **审核结果**：2026-09-10 Owner 确认选型，主线会话 **批准记录**。

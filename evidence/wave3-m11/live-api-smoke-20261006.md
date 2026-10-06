# Owner-authorized live API smoke checks (2026-10-06)

## Scope and Authorization

- Baseline: main at `8a9064c`. This is a local supplier protocol check, not an application or Agent acceptance run.
- The Owner selected real chat, embedding, rerank and official cloud PDF parsing services. Only synthetic or public nonsensitive samples are authorized; no enterprise documents were sent.
- The Owner confirmed the chat account had been recharged, then explicitly requested direct calls without implementing billing or waiting for a price screenshot.
- The previously stated CNY 10 round budget was not turned into a production default. Actual deductions were not queried or calculated, and there was no enforced monetary cap. Do not claim this run proves a CNY 10 hard limit.
- Requests were bounded by output lengths and deadlines, with no automatic retries or model fallback. Modified diagnostic requests are listed separately below.
- Credentials were read locally from the ignored private template through Node's `util.parseEnv`. No credential values, authenticated request headers, account identifiers, signed URLs or supplier base URLs are included here.

## Observations

Ten authenticated business API requests were attempted. Public documentation fetches are not included in this count.

| Check | Requested Model | HTTP | Observed Result |
| --- | --- | --- | --- |
| Qwen minimal chat | `qwen3.8-flash` | 200 | Returned exactly `OK`; requested and returned model IDs matched. |
| Qwen forced tool, default thinking behavior | `qwen3.8-flash` | 400 | `invalid_request_error`; no tool execution or fallback. |
| Qwen same forced tool with `enable_thinking=false` | `qwen3.8-flash` | 200 | Returned `pivot_probe` with JSON arguments matching the supplied schema. |
| GPT minimal Responses request | `gpt-6.1-sol` | 200 | Returned exactly `OK`. |
| Grok minimal Chat Completions request | `grok-4.7` | 200 | Did not meet the exact `OK` assertion. Do not describe this as a transport failure or exact-answer success. |
| Embedding | `BAAI/bge-m3` | 200 | One finite 1024-dimensional vector for one short synthetic sentence. |
| Rerank | `BAAI/bge-reranker-v2-m3` | 200 | Two finite scores and valid document indices; the relevant sentence ranked first. |
| MinerU batch upload authorization | `vlm` request parameter | 401 | Rejected at submission; no PDF upload, polling, result download or parsing task was started. |
| GPT forced Responses tool | `gpt-6.1-sol` | 200 | One valid function call with nonempty call ID and schema-matching arguments. |
| Grok automatic tool selection | `grok-4.7` | 200 | One valid function call with nonempty call ID and schema-matching arguments. |

The tool schema has one required `marker` string fixed to `pivot-test`, forbids additional properties, and names the function `pivot_probe`. These checks validated returned tool-call structure only: the tool was not executed and no tool-result continuation was sent. A complete multi-step ReAct loop remains untested.

Qwen's diagnostic pair differed only by `enable_thinking=false`. The successful forced-tool request used an output limit of 128 tokens. GPT and Grok tool probes used limits of 256 and 128 respectively. These are one-off diagnostic limits, not approved runtime defaults.

Chat credentials were used independently. Explicit provider errors did not trigger fallback. The probes did not test automatic fallback classification, streaming, resumable Runs, fixed model snapshots, administrator switching or permission/egress gates.

## Local Configuration and Safety

- Qwen's private preparation settings now use the verified Chat Completions base path and `openai-completions` protocol. The template records the forced-tool thinking observation as a comment.
- The private template now contains the exact successful embedding and rerank IDs. The observed vector dimension is not a production schema or index-dimension freeze.
- MinerU's official v4 base path is prepared locally, but its token did not authenticate. Local token inspection found no duplicated `Bearer` prefix or internal whitespace; expiration was not established. HTTP 401 alone does not distinguish an invalid, expired, revoked or wrong-service token.
- The original `.env` was not modified. The private file has mode 600, and both the private file and its visible symlink remain Git-ignored.
- `PIVOT_LIVE_*` settings are preparation fields, not automatically loaded runtime settings. No application code, database, business contract, dependency lock or production budget setting changed.
- API requests rejected redirects. The PDF probe was prepared to keep the API token out of object-storage upload/download requests and to bound result size, but submission failed before those stages. Storage-host handling and result extraction therefore have no live success evidence.

## Verification and Remaining Work

Executed existing private-configuration safety regression:

```text
.venv/bin/python -m pytest tests/integration/pipeline/test_NFR_OBS_compose_staging.py -q
22 passed, 1 skipped in 1.51s
```

The skipped case depends on an unavailable live staging deployment. This regression does not validate the provider adapters or the new Agent.

The commands above were inline local diagnostic runners, not committed reusable live harnesses. They did not install dependencies or execute the application's HTTP provider adapters. No full regression, browser, real database, LangGraph or end-to-end ingest/retrieval/answer acceptance run was performed.

Next: replace or renew the official MinerU API token locally, then explicitly rerun the bounded synthetic PDF check. Do not silently retry the rejected credential. Preserve the distinction between direct supplier protocol checks and approved runtime integration.

All ND-AGENT proposal approvals, production budget/checkpoint contracts, DR-010/DR-011, ticket DoR and GATE-P0 decisions remain unchanged.

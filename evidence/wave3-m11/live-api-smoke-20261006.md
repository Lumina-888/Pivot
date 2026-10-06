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

## MinerU Retest After Owner Credential Update

After the Owner reported updating the private Token, a fresh bounded probe was run from main at `317e6a8`. This adds one authenticated submission request to the initial ten; no chat, embedding or rerank requests were repeated.

- The visible private entry was reloaded using `util.parseEnv`; the Token assignment was unique and nonempty. File mode 600, the symlink target and both Git-ignore checks passed.
- The Token had no extra `Bearer` prefix or internal whitespace and did not equal another configured provider credential. Its expiration could not be established; these checks do not prove validity or that the value changed from the previous attempt.
- A one-page synthetic PDF was generated in memory (863 bytes). Submission to the official v4 batch upload interface again returned HTTP 401. Submission count: 1; uploads, polls, downloads and automatic retries: 0. No batch ID or parsing task was obtained.
- The redacted diagnostic state is retained locally at `.pi/artifacts/mineru-live-20261006-retest/state.json`, which is Git-ignored. No credential, authorization header, signed URL or document content was stored in that artifact.
- The updated credential remains blocked at authentication. No production code, budget contract or service configuration was changed, and no alternative endpoint or authentication bypass was attempted.

## MinerU Read-only Authentication Diagnosis

The Owner subsequently confirmed the Token was newly created and enabled, and requested continued diagnosis. One authenticated GET queried the official v4 batch-result interface using a randomly generated, nonexistent batch identifier. It returned HTTP 401 with the sanitized JSON message `user authenticate failed`. No submission, PDF upload, status polling, result download, retry or alternate supplier was used. Total authenticated API attempts across these rounds: 12 (the previous 11 plus this one read-only diagnostic query); public documentation fetches are excluded.

Secret-safe local checks found no surrounding quotes, whitespace, non-ASCII characters, three-dot or Unicode ellipsis masks, asterisk masks or obvious placeholder. The value is longer than twenty characters, does not have UUID shape and is not a decodable JWT. None of these observations establishes validity, expiry, account association or a required token format.

Public official API-management frontend code confirms the v4 Bearer authorization convention. Its token-creation success dialog copies the returned full token; the token table masks display values and conditionally offers copying for values longer than twenty characters without `...`. The current local value does not match those obvious masking indicators, so a masked copy is not established as the cause. No signed-in browser session, token-management API or personal account data was accessed.

Official documentation distinguishes authenticated precision parsing v4 from a separate unauthenticated lightweight Agent parsing API. The latter was not called: it would not diagnose v4 authentication or validate the requested `vlm` workflow.

The read-only failure shows submission payload/PDF content is not needed to reproduce the authentication rejection. It does not prove whether the credential, account configuration, transport or provider authentication service is responsible. Next: confirm whether the local value came from the creation-success dialog's Copy Token action, without sending it in chat. A new PDF probe requires an explicitly confirmed credential correction or a concrete new diagnostic hypothesis; do not repeat this rejected credential automatically. Preserve the distinction between direct supplier protocol checks and approved runtime integration.

Documentation-only diagnosis verification: the same private-configuration safety regression passed again (22 passed, 1 skipped in 1.04s); `git diff --check`, configured-secret scans of the three changed documents, private mode 600 and both actual Git-ignore checks passed. No application code or private credential was changed.

All ND-AGENT proposal approvals, production budget/checkpoint contracts, DR-010/DR-011, ticket DoR and GATE-P0 decisions remain unchanged.

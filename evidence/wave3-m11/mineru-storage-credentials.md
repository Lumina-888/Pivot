# MinerU storage credential isolation (2026-10-06)

## Scope and Readiness

Baseline: main at `b53f3c7`. The Owner explicitly approved testing the existing public `MinerUCloudParser.parse()` interface with controlled HTTP fixtures: submission/polling must retain Bearer API authentication; upload/result download must not receive that API credential. This is a narrow defect correction in the existing parser, not new Agent business implementation or a public contract change.

- M07 owns `api/src/pivot/parsing/mineru.py` and `tests/unit/worker/test_FR_DOC_004_mineru.py`; M11 records evidence and existing integration/security regression results. The mainline session updates both module progress files and root progress.
- Existing injected client signatures, Worker schema, error codes, document states, model settings, permissions and dependency versions remain unchanged. No new production defaults or ADR decisions are introduced.
- Private configuration, unrelated Owner approval drafts, CI and live services were not modified. No real credential or supplier request was used in this slice.

## Cause and Fix

The parser reused the API authorization mapping for `put_bytes()` and `get_bytes()` calls to returned storage URLs. That forwarded the Bearer API Token outside its intended API request boundary, including when the storage URL happened to use the same origin.

Upload and ZIP download now receive an empty header mapping. API submission and status polling still receive the Bearer authorization mapping. Provider-returned signed URLs are passed through unchanged; bytes, request timeouts and document parsing behavior remain unchanged.

The scripted HTTP boundary fixture records outgoing headers; no parser-private method is called by the tests. The two new parametrized tests cover same-origin and different-origin signed storage URLs. They also assert successful document parsing, unchanged signed URL/timeout handling and authenticated API calls. Existing fake Token literals are nonfunctional fixture data, not real credentials.

## Red, Green and Regression

1. Upload isolation: `pytest tests/unit/worker/test_FR_DOC_004_mineru.py -k upload_does_not_send_api_token -q` produced **2 failed / 16 deselected**, because the upload headers included the fixture Bearer Token. After changing only the upload call to pass empty headers, the same selection produced **2 passed / 16 deselected**.
2. Download isolation: the corresponding `-k download_does_not_send_api_token` selection produced **2 failed / 18 deselected** on the leaked download header. After changing only the download call, the complete parser test file produced **20 passed** (including the four new parameter cases).
3. The existing dynamic test-constructor dictionary received a `dict[str, Any]` annotation and literal syntax, eliminating nine LSP argument-type inference findings without changing its behavior or suppressing diagnostics.

Broader affected regression:

```text
.venv/bin/python -m pytest tests/unit/worker tests/integration/pipeline/test_FR_DOC_004_mineru_parser.py tests/integration/pipeline/test_NFR_OBS_compose_staging.py tests/security/ops -q
238 passed, 1 skipped, 2 warnings in 22.86s
```

The skip requires unavailable live staging. The warnings are existing Starlette/httpx and AnyIO deprecations. The integration fixtures exercise both API upload/ingest composition and worker assembly; they are not live supplier acceptance.

```text
.venv/bin/python -m ruff check --config api/pyproject.toml api/src/pivot/parsing/mineru.py tests/unit/worker/test_FR_DOC_004_mineru.py
All checks passed!

.venv/bin/python -m compileall -q api/src/pivot/parsing/mineru.py tests/unit/worker/test_FR_DOC_004_mineru.py
exit 0
```

Active LSP probes on both changed Python files completed with zero diagnostics. The first parser probe timed out; a subsequent ten-second probe completed clean. An automatic project scan reported dependency-resolution findings in neighboring unchanged modules; the project virtual environment can import `jsonschema`, `fitz` and `pytest`. This slice does not claim a clean full-project type-check. No neighboring business modules were changed, and no diagnostics were disabled or suppressed.

Final checks: `git diff --check`, a credential-pattern scan of the changed material, 83 local Markdown links and the private file's mode 600/two actual Git-ignore checks passed. The credential-pattern scan does not inspect or compare private credential values; private configuration contents were not read. Untracked Owner approval drafts remain untouched.

## Remaining Work

This fixes direct storage-call credential forwarding at the parser's injected HTTP boundary. It does not add an application-level storage host policy, redirect policy, archive-size policy or new production polling limits; those remain separately scoped concerns. No claim is made that the transport is a complete egress/SSRF boundary.

The earlier [synthetic live supplier probe](live-api-smoke-20261006.md) passed after the Owner corrected the Token source. That probe did not execute the application adapter; this slice did not repeat live calls. A future bounded application-adapter live test remains necessary before describing application integration as live-verified. Complete ingest/retrieval/answer, real database, browser and LangGraph acceptance were not run.

Agent proposal approvals, DR-010/DR-011, production budget/checkpoint contracts, ticket DoR and GATE-P0 remain unchanged. No production readiness or new Agent acceptance is inferred from these fixture regressions.

# Wave 3 M05/M08 SSE 长连接限制

环境：HTTP TestClient 覆盖创建后非终态返回、反缓冲响应头与 Last-Event-ID 补发；EventLog 等待与逐帧 yield 为进程内夹具。uvicorn 长连接为 opt-in（`PIVOT_REQUIRE_SSE_LIVE=1`）；CI 默认 skip，不启动 uvicorn/Next/Compose。

- `POST /runs` 立即返回 `initial_state.state=received`，编排在 BackgroundTasks 中执行并 commit。
- `GET /runs/{id}/events` 按帧推送；未终态时保持生成器；注释行 keepalive 不是冻结的 SSE 预算。
- Next `app/api/v1/runs/[id]/events` 透传上游 `body`，设置 `Cache-Control: no-cache, no-transform` 与 `X-Accel-Buffering: no`。
- 事件仍不含思考链/系统 Prompt。Claim/Citation 仍不入库。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-004 | unverified | SSE 长连接是 TestClient/opt-in uvicorn 夹具，不是 Verifier 盲评或企业 Golden Set；阈值仍 TBD-P0 |

`implemented`（长连接夹具）≠ `verified`。

# Wave 3 M11 100k Chunk opt-in 夹具限制

环境：进程内 Fake KeywordRetriever；不启动 Compose/uvicorn；无真实索引；无 ECS 4C8G。

- `PIVOT_CHUNK_COUNT` 必须注入；CI 只用小 N。
- 100k 为 opt-in：`PIVOT_REQUIRE_100K=1` 且 `PIVOT_CHUNK_COUNT=100000`；CI 默认 skip。
- 可记录 tracemalloc peak，**不**作为门禁，不冻结 P95/内存阈值（仍为 `TBD-P0`）。
- 不是 Qdrant 100k 索引峰值，不是 5 并发问答压测。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-007 | unverified | opt-in 100k Fake retrieve ≠ ECS 资源峰值 / 真实索引压测 |

`implemented`（opt-in harness）≠ `verified`。

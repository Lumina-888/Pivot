# Wave 3 M11 5 并发与进程内备份恢复限制

环境：进程内 Fake/内存 client；不启动 Compose/uvicorn；无新 ECS；无加密 OSS。

- 5 并发夹具对 `RetrievalService.retrieve` 同时发起 5 路（`NFR-CAP-002` 已定容量）；断言完成与证据，不采集 P50/P95。
- 合成 Chunk 生成器接受注入 `count`；CI 只用小 N。100k opt-in 夹具见 `chunk-capacity.md`。
- `ops/fact_backup.py` 备份用户目录、对象字节、向量点、审计；Redis 为可重建状态，不进事实包。
- 恢复后可核对用户、对象、向量 payload 与 `ops.backup_restore` 审计；**不是** `NFR-DR-004` 新 ECS 演练。
- RPO/RTO、P95、100k 峰值仍为 `TBD-P0` / 未实测。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-006 | unverified | 进程内 roundtrip 不是加密 OSS + 新 ECS 恢复 |
| GATE-P0-007 | unverified | 5 路 Fake 检索完成 ≠ 5 并发问答压测 / 100k Chunk 资源峰值 |

`implemented`（in-process fixture）≠ `verified`。

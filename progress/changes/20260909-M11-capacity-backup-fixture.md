# 变更申请：M11 5 并发夹具与进程内备份恢复

- **日期**：2026-09-09
- **申请人**：Wave 3 主线会话（M11 性能/灾备夹具）
- **背景**：检索 dense 已消费 Qdrant。Wave 3 下一刀是 5 并发 / 备份恢复。SPEC `NFR-CAP-002` 已定为在线问答不超过 5 并发；`NFR-CAP-004` 目标 100k Chunk 需 P0 验证；`NFR-DR-001~004` / `GATE-P0-006` 要求加密 OSS + 新 ECS 演练后冻结 RPO/RTO。CI 不得启动 Compose；不得把 Fake/进程内夹具标成 GATE verified。
- **原契约/现状**：
  - `tests/performance/PLAN.md` 仅声明 unverified；无 5 并发执行夹具；
  - `ops/runbook-backup-restore.md` 为未演练草稿；无进程内事实备份/恢复；
  - `GATE-P0-006` / `GATE-P0-007` 均 unverified。
- **拟变更内容**（本切片）：
  - M11 增加 **5 并发** 检索夹具：注入并发数 5（`NFR-CAP-002` 已定容量），线程同时 `retrieve`；断言全部完成且有证据；**不** 断言 P95/首 Token，不冻结 `NFR-PERF-*`；
  - 增加 **参数化** 合成 Chunk 生成器：测试只跑注入的小 N；**不** 在 CI 生成 100k，不把 100000 写成默认值；
  - `ops/fact_backup.py`：按 SPEC §9.3 备份 **事实源**（用户目录 / 对象 / 向量点 / 审计）；Redis 列为可重建、不进事实包；进程内 roundtrip（memory client）；恢复后可核对用户、对象字节、向量 payload、审计；
  - 恢复路径记录 `ops.backup_restore` 审计动作（既有目录，不改契约）；
  - 更新 runbook / PLAN，写明 **不是** 新 ECS、**不是** 加密 OSS；**不** 把 `GATE-P0-006` / `GATE-P0-007` 标 verified。
- **影响模块**：M11（ops 夹具、performance/pipeline 测试、证据、runbook）；M03/M04/M06 只消费既有端口；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：默认 CI 跑进程内夹具（无 Docker）；既有 capacity plan 断言仍要求 unverified。
- **测试 ID**：`test_NFR_CAP_002_five_concurrent_retrieves_complete`、`test_NFR_CAP_002_does_not_freeze_latency`、`test_NFR_CAP_004_chunk_count_is_injected`、`test_GATE_P0_007_not_verified_by_five_concurrent_harness`、`test_NFR_DR_restore_roundtrip_users_objects_vectors_audit`、`test_NFR_DR_redis_is_not_a_fact_in_backup`、`test_NFR_DR_restore_records_backup_audit`、`test_NFR_DR_does_not_freeze_rpo_rto`、`test_GATE_P0_006_not_verified_by_in_process_restore`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不冻结 RPO/RTO/P95/100k）。
- **审核结果**：2026-09-09 Wave 3 主线会话 **批准**。

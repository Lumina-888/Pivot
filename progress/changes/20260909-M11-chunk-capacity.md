# 变更申请：M11 100k Chunk opt-in 容量夹具

- **日期**：2026-09-09
- **申请人**：Wave 3 主线会话（M11 性能夹具）
- **背景**：5 并发 retrieve 夹具已有。SPEC `NFR-CAP-004` 目标 100,000 Chunk 需 P0 验证；`GATE-P0-007` 仍 unverified。上一刀容量夹具明确：生成器按注入 count 工作，CI 不生成 100k，不把 100000 写成 `synthetic_chunks` 默认值。本切片补 **opt-in** 100k 检索夹具，不冻结 P95/内存阈值，不标 GATE verified。
- **原契约/现状**：
  - `ops/fact_backup.py` 的 `synthetic_chunks(count=)` 已参数化；CI 只用小 N；
  - `tests/performance/PLAN.md` 写明无 100k 索引峰值；
  - 无 `PIVOT_REQUIRE_100K` 门闩，无独立 100k runner。
- **拟变更内容**（本切片）：
  - 新增 `ops/chunk_capacity.py`：`PIVOT_CHUNK_COUNT` 必须注入，缺省失败闭环；**不是** `synthetic_chunks` 的默认 100000；
  - `PIVOT_REQUIRE_100K=1` 时要求 `PIVOT_CHUNK_COUNT=100000`（SPEC `NFR-CAP-004` 目标），否则失败闭环；未设该旗标时 100k 测试 skip；
  - 夹具对注入语料跑一次 Fake `retrieve`，断言完成与证据；可用 stdlib `tracemalloc` **记录** peak，**不** 断言内存/P95 上限；
  - CI / `ops/run_grouped_tests.py` **不** 设置 `PIVOT_REQUIRE_100K`；
  - 更新 PLAN / 证据：opt-in 夹具存在 ≠ ECS 4C8G 压测，**不** 把 `GATE-P0-007` 标 verified。
- **影响模块**：M11（ops 夹具、performance 测试、证据、PLAN）；M04 只消费既有 `RetrievalService`/`KeywordRetriever`；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：既有 `test_NFR_CAP_004_chunk_count_is_injected` 仍断言 `fact_backup.py` 不含 100000；5 并发夹具不变。
- **测试 ID**：`test_NFR_CAP_004_chunk_count_requires_injection`、`test_NFR_CAP_004_small_corpus_retrieve_completes`、`test_NFR_CAP_004_require_100k_rejects_wrong_count`、`test_NFR_CAP_004_one_hundred_k_retrieve_when_required`、`test_NFR_CAP_004_does_not_freeze_peak_or_p95`、`test_NFR_CAP_004_ci_does_not_require_100k`、`test_GATE_P0_007_not_verified_by_one_hundred_k_harness`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不冻结 P95/内存/ECS 规格）。
- **审核结果**：2026-09-09 Wave 3 主线会话 **批准**。

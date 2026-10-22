# ND-GAP-01 真实接线证据

日期：2026-10-22。基线：`main@a1d2bab` 本地工作副本。环境：Python 3.12，仓库虚拟环境，分组回归口径与 CI 一致（`--skip-web`）。

## 缺陷复现（修复前）

进程内脚本构造 `RunService` 并创建一个 Run 后调用四个计数方法：

- `count_total` 返回 1。
- `count_completed`、`count_failed`、`count_in_progress` 均抛 `AttributeError: 'RunRecord' object has no attribute 'status'`。

## 修复后验证

同脚本重跑：四个方法返回 `1 0 0 1`。以同一 store 新建第二个 `RunService` 实例，计数一致，证明计数来自持久存储而非进程缓存。

## 测试结果

- 目标测试 15 项全过：`tests/integration/db/test_M03_run_store.py`、`tests/integration/db/test_M03_document_store.py`、`tests/integration/pipeline/test_ND_GAP_01_admin_metrics_tasks.py`（含新增 4 项）。
- 全量分组回归通过：`python ops/run_grouped_tests.py --skip-web`，输出 `grouped checks passed (not GATE-P0 verified)`。
- `ruff check`（api 与 worker 等 CI 口径路径）全过，`compileall` 全过。

## 口径说明

- 计数分桶口径与修复前代码一致，只换数据源。
- 任务列表数据源为 `celery_tasks` 持久表，未新造事实源。
- 本证据为本地与 CI 形态验证，不构成 GATE-P0 验证。

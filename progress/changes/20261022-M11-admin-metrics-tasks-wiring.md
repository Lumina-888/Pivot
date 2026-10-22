# ND-GAP-01：后台指标与任务真实接线

> **工单**：ND-GAP-01
> **日期**：2026-10-22
> **Accountable**：M11
> **Contributors**：M00、M03、M05、M06、M07、M10
> **输入**：`a1d2bab`（`main`）
> **输出**：（待提交）
> **前置**：`20261012-M11-admin-metrics-tasks.md`（初版路由与占位响应）

## 0. 目标与非目标

### 目标

1. `/admin/metrics` 的问答计数改读持久化 Run 存储，进程重启后不丢失，跨进程可见。
2. `/admin/tasks` 返回 `celery_tasks` 持久表中的真实入库任务。
3. 修复问答计数误读字段导致的潜伏崩溃（见第 3 节）。

### 非目标

- 不冻结分页参数与指标阈值，仍为 `TBD-P0`。
- 不新造任务事实源，不改任务状态机与权限口径。
- 不更改四页后台范围。

## 1. 契约修订（Owner 于 2026-10-22 确认）

`GET /admin/tasks` 的响应由初版占位修订为：

```json
{
  "items": [
    {
      "task_id": "task_xxx",
      "entity_type": "document_version",
      "entity_id": "ver_xxx",
      "attempt": 1,
      "state": "queued",
      "retryable": false,
      "created_at": "2026-10-22T02:00:00+00:00"
    }
  ],
  "pagination": null
}
```

- 顶层键名由 `tasks` 改为 `items`，字段与前端 `AdminTaskList` 类型一致（`web/features/admin/types.ts`）。前端概览页是该接口的唯一消费者。
- `created_at` 取 `celery_tasks.created_at`。记录无时间时为 `null`，不伪造。
- 排序为创建时间倒序，同刻以 `id` 倒序为次序。
- `pagination` 保持 `null`。分页参数未冻结，后续补分页须另行登记。

## 2. 实现

- `RunStore` 协议新增 `status_counts`。内存实现按 `RunRecord.state` 计数，SQLAlchemy 实现按 `runs.state` 分组计数。
- `RunService` 的四个计数方法全部改走 `status_counts`，分桶口径不变：`completed` 单列，`failed` 含 `failed/refused/uncertain`，进行中含 `received/retrieving/drafting/verifying`。原进程内缓存计数与 `hasattr` 探测一并删除。
- `TaskStore` 协议新增 `list_all`。`SqlAlchemyTaskStore` 按创建时间倒序返回，映射补齐 `created_at`；`TaskRecord` 新增可空字段 `created_at`。
- `DocumentService` 新增 `list_tasks` 透传。管理路由新增 `TaskSource` 注入，装配点在 `create_app`，取值为文档服务。

## 3. 缺陷说明

旧计数代码读取 `RunRecord.status`，该字段不存在，实际字段为 `state`。Run 数为零时生成器不求值，缺陷被掩盖。任一 Run 存在时，`count_completed`、`count_failed`、`count_in_progress` 均抛 `AttributeError`，接口返回 500。本切片以 HTTP 层回归测试锁定该场景。

## 4. 测试与证据

- `test_NFR_OBS_005_admin_metrics_counts_existing_runs`：HTTP 层计数正确性与崩溃回归。
- `test_NFR_OBS_005_admin_tasks_read_persisted_facts`：票面测试，任务列表读持久事实。
- `test_NFR_OBS_005_run_status_counts_from_persisted_rows`：SQL 存储计数，新服务实例读旧数据。
- `test_NFR_OBS_005_task_store_list_all_returns_persisted_tasks`：任务存储 `list_all` 与字段映射。
- 既有 `test_NFR_OBS_006_admin_tasks_returns_structure` 已按新契约更新。
- 证据见 `evidence/wave3-m11/admin-metrics-tasks-wiring.md`。

## 5. 风险与残余

- 任务列表一次全部返回，行数随历史任务总数增长。分页与过滤待 `TBD-P0` 冻结后另行切片。
- 指标为全量计数，无时间窗参数。阈值与告警不在本票范围。

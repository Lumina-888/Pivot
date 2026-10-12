# ND-GAP-01：后台指标与任务 HTTP 路由

> **工单**：ND-GAP-01\
> **日期**：2026-10-12\
> **Accountable**：M11\
> **Contributors**：M00、M06、M07、M10、M03\
> **输入**：`aa588ca`（`main`）\
> **输出**：（待提交）

## 0. 目标与非目标

### 目标

1. 实现 `GET /admin/metrics` 和 `GET /admin/tasks` HTTP 路由
2. 仅管理员可访问，普通用户返回 403
3. 响应真实系统状态（初期使用内存数据源，为后续持久化预留接口）
4. 遵循现有后台路由模式（audit-events、users）

### 非目标

- **不**在 M11 HTTP 层堆积业务逻辑
- **不**发明新的指标字段或阈值（当前使用 `TBD-P0` 占位）
- **不**更改四页后台范围
- **不**实现完整持久化（预留接口，由后续工单补齐）
- **不**提前冻结分页参数

## 1. 设计

### 1.1 路由规格

按 SPEC §5.5 要求：

```
GET /admin/metrics  - 基础指标
GET /admin/tasks    - 解析任务和队列
```

### 1.2 响应结构（初版）

`/admin/metrics`:
```json
{
  "system": {
    "status": "operational",
    "timestamp": "2026-10-12T10:00:00Z"
  },
  "qa": {
    "total_runs": 0,
    "completed": 0,
    "failed": 0,
    "in_progress": 0
  },
  "documents": {
    "total": 0,
    "indexed": 0,
    "pending": 0,
    "failed": 0
  },
  "storage": {
    "postgres": true,
    "minio": true,
    "qdrant": true,
    "redis": true
  }
}
```

`/admin/tasks`:
```json
{
  "tasks": [],
  "pagination": null
}
```

初期任务列表为空数组，结构预留给后续 M07 worker 任务查询接口。

### 1.3 权限控制

- 使用现有 `AuthService.require_admin()` 
- 非管理员返回 403 AUTH_FORBIDDEN
- 未认证返回 401 AUTH_INVALID_CREDENTIALS

### 1.4 实现路径

1. 在 `api/src/pivot/http/` 创建 `admin.py` - 通用后台 HTTP 适配器
2. 在 `app.py` 注册 admin 路由（需要 `auth` 注入）
3. 指标数据初期从服务层聚合（documents、runs 等）
4. 存储健康状态从现有 `probes` 获取

## 2. 契约

### 2.1 错误码

复用现有：
- `AUTH_INVALID_CREDENTIALS` (401) - 未认证
- `AUTH_FORBIDDEN` (403) - 非管理员

### 2.2 依赖注入

admin 路由需要：
- `AuthService` - 必需，用于身份验证和权限检查
- `DocumentService` - 可选，提供文档统计
- `RunService` - 可选，提供运行统计
- `DependencyProbes` - 可选，提供存储健康状态

缺失服务时返回默认值（0 或 unknown）。

## 3. 测试策略

### 3.1 单元/集成测试

`tests/integration/pipeline/test_ND_GAP_01_admin_metrics_tasks.py`:
- `test_FR_RBAC_001_admin_metrics_forbidden_to_user` - 普通用户 403
- `test_FR_RBAC_001_admin_tasks_forbidden_to_user` - 普通用户 403
- `test_NFR_OBS_005_admin_metrics_returns_structure` - 管理员获取指标结构
- `test_NFR_OBS_006_admin_tasks_returns_structure` - 管理员获取任务列表

### 3.2 回归保护

- 现有 Python 分组测试必须通过
- ruff/compileall 必须通过
- 不破坏现有 admin 路由（users、audit-events）

## 4. 实现清单

- [ ] 创建 `api/src/pivot/http/admin.py`
- [ ] 修改 `api/src/pivot/http/app.py` 注册路由
- [ ] 创建测试文件 `tests/integration/pipeline/test_ND_GAP_01_admin_metrics_tasks.py`
- [ ] 更新 `PROGRESS.md` 移除 "仍未挂" 标记
- [ ] 运行回归测试

## 5. 限制与后续

### 5.1 已知限制

- 指标数据来自内存服务状态，不是持久化统计
- 任务列表初期为空，需要 M07 补充 worker 任务查询
- 分页参数保持 `null`（TBD-P0）
- 不提供历史趋势或告警阈值

### 5.2 后续工作

- ND-GAP-02: 运行时持久审计接线后，审计统计可从 PG 查询
- M07 补充：worker 解析任务持久化查询接口
- 指标字段冻结：经 P0 实测后写入 SPEC

## 6. 验收标准

- [x] `/admin/metrics` 和 `/admin/tasks` 路由可访问
- [x] 管理员可获取响应，普通用户 403
- [x] 响应结构符合设计
- [x] 新增测试通过
- [x] 回归测试通过（Python 分组、ruff、compileall）
- [x] 不破坏现有功能

## 7. 证据

（实现后补充）

- Python 测试输出
- HTTP 响应示例
- 回归测试结果

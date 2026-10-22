# ND-GAP-02 审计统一落库与分级失败策略（2026-10-22）

## 背景

`audit_events` 事实表早已存在，但运行时三套审计（认证、文档、统一审计服务）分别写入进程内存：API 进程的文档审计、认证审计重启即丢且不可查；worker 入库装配的文档审计更是空实现，事件被直接丢弃。工单 ND-GAP-02 要求关键审计写同一 PG 事实接口、重启后可按 request_id 或 run_id 复盘。本变更登记落库映射与失败写入策略，不改审计字段、动作词汇与脱敏口径。

## 决定（Owner 2026-10-22 确认）

审计失败写入策略为分级处理：

1. 安全关键事件 fail-closed，审计写失败时业务操作被拒绝：动作以 `auth.`、`authz.`、`export.` 为前缀者，以及 `document.delete`。
2. 一般事件 best-effort：`qa.run`、`document.upload`、`document.update`、`document.retry` 等。写失败时业务继续，但必须经进程内计数器计数并写结构化错误日志，不得静默丢弃；返回的事件对象在该情形下未落库，管理端列表与复盘查不到，以计数为准观测丢失量。

分级以 `audit/catalog.py` 的规范动作名（含别名归一）判定，实现在 `audit/policy.py`。

## 落库映射

1. 新增 `db/audit.py`：`SqlAlchemyAuditStore` 实现统一审计存储接口（append、get、list、query）；`SqlAlchemyAuthAuditSink` 与 `SqlAlchemyDocumentAuditSink` 把认证与文档的审计草稿映射为审计事件（动作经 catalog 归一、元数据经现行脱敏规则处理、时间取写入时刻）。
2. 装配切换：`PIVOT_STORAGE=postgres` 时，API 装配的三套审计全部落 `audit_events`；worker 入库装配的文档审计由空实现改为同一落库适配并套分级策略包装。内存装配（测试与本地）保持原内存实现，文档审计同样套分级包装（内存实现不失败，包装无副作用）。
3. 管理端审计列表与 Run 复盘读同一事实表，落库后认证、文档事件与问答、导出事件同表可查。

## 不变与待定

1. 审计事件字段、动作词汇、脱敏规则不变；append-only 语义不变（重复编号拒绝写入，应用层另有 before_flush 监听器拒绝更新与删除）。
2. 数据库层权限收紧（撤销应用角色对 audit_events 的 UPDATE 与 DELETE 权限）属部署事项，归 ND-STG-04-A，不在本变更内。
3. best-effort 失败计数为进程内计数，多实例聚合观测归后续可观测建设，不在本变更内冻结口径。

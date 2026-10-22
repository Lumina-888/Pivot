# ND-GAP-02 证据：审计统一落库与分级失败策略

日期：2026-10-22。基线：main@8794de7。契约记录：`progress/changes/20261022-M06-audit-persistence-tiered-failure.md`。本证据为 sqlite 替身与单元替身验证，非真实 PG、非 GATE-P0 verified。

## 侦察结论（改前事实）

1. `audit_events` 表与领域记录一一对应，模型层已有 before_flush 监听器拒绝更新与删除。
2. 运行时三套审计均为进程内存：认证 `InMemoryAuthAudit`、文档 `MemoryDocumentAudits`、统一服务 `AuditService(AppendOnlyAuditStore())`；`audit/store.py` 自述「Production persists via M03」，SQL 存储从未实现。
3. worker 入库装配（`pivot_worker/assembly.py`）的文档审计为空实现 `_NullAudits`，入库链路产生的文档审计事件被直接丢弃。
4. 认证与文档审计草稿字段同形（actor、action、target、result、request_id、metadata），可统一映射。

## 实现摘要

1. `audit/store.py` 新增 `AuditStore` 协议，`AuditService` 改按协议注入并内置分级失败处理（关键动作写失败上抛，一般动作计数并记日志后返回未落库事件）。
2. `audit/policy.py`（新）：关键动作判定（`auth.`、`authz.`、`export.` 前缀与 `document.delete`，经 catalog 别名归一）、`AuditWriteFailures` 计数器、`TieredAuditSink` 包装器。
3. `db/audit.py`（新）：`SqlAlchemyAuditStore`（重复编号抛 append_only）与认证、文档两个落库 sink 适配器（动作归一、元数据脱敏）。
4. `http/bootstrap.py`：存储开关新增 audit_store 与两套 sink 的 SQL/内存双分支；文档审计统一套 `TieredAuditSink`；`AuditService` 注入同一事实存储与共享计数器。
5. `pivot_worker/assembly.py`：删除 `_NullAudits`，文档审计改为落库适配加分级包装。

## 验证

1. 新增 `tests/integration/db/test_M06_audit_persistence.py` 四项：统一服务、认证 sink、文档 sink 写入后以新实例读回（重启替身）动作序列与按 request_id、run_id 查询；`replay` 返回模型与提示版本；已落库事件更新与删除被应用层拒绝；SQL 存储重复追加被拒。
2. 新增 `tests/unit/audit/test_FR_AUDIT_002_tiered_failure_policy.py` 四项：关键动作分类（含别名归一）、关键事件写失败 fail-closed 且不计数、一般事件写失败计数为 1 且业务继续、文档 sink 包装器对删除动作上抛而对上传动作计数放行。
3. 全量分组回归（`ops/run_grouped_tests.py --skip-web`）、ruff 与 compileall 全绿。

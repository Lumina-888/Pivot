# 2026-11-03 联调复测结果与问题清单

> 版本：v1.0（2026-11-04）。本文件是本次联调复测的**完整记录**：实测结果、实测数字、问题清单、未测项与需求规格。
> 本文只记录问题与证据，**不含任何代码修改**；`api/`、`worker/`、`web/`、`tests/` 本轮零改动。
> 依据：[联调测试技术文档](../docs/联调测试技术文档.md)、[待测试任务清单](../progress/待测试任务清单.md)。
> 本文测试通过不等于 GATE-P0 通过，`GATE-P0-001~008` 仍全部 unverified，也不改变任何 `TBD-P0` 或 DR 状态。

## 1. 结论摘要

| 维度 | 结果 |
| --- | --- |
| 部署检查 | `/healthz` 200；`/readyz` 四项全 true（postgres/minio/qdrant/redis，Silo 让 minio 首次为 true）；迁移单头 `c8842fce3b98`，31 张表 |
| 分组回归（任务 9） | 1806 passed / 89 skipped / 0 failed；ruff `All checks passed!`；compileall 通过 |
| 真实 PG 组（任务 9） | 50 passed（351.91 s） |
| 已登记缺陷 1、3、4、7 | **4/4 通过** |
| 缺陷 2 任务 1、2、3、5、6、7、8、9 | **8/8 通过**（任务 4 无 HTTP 入口，见 §13） |
| 全链路任务 10、11 | **通过**（sync 与 Celery 跨进程均免重启可见） |
| 任务 12 全链路 | 部分：上传、解析、认领、移动、删除、取消、重启已跑 |
| 任务 13 四项指标 | 引用错误率 **0.0**、过期规则 **5/5**、租约 fencing **5/5**、预算对账 **账本自洽但漏记 writer 调用** |
| Agent Golden Set（真实模型） | 评测装配 **8/10**；生产 writer 装配 **5/10 answered**，多次运行 4~7 条 answered，citation 错误恒为 0 |
| 缺陷 5、6 | **未通过**（缺陷 5 未闭合；缺陷 6 被新缺陷阻断） |
| 本轮问题 | **16 项**：P1 六项、P2 七项、P3 三项；其中 1 项已降级为“已解释观察” |

## 2. 环境与装配

| 项目 | 实测值 |
| --- | --- |
| 仓库基线 | `main` `eaf8aef`（拉取后工作区干净） |
| 被测对象 | 本机 loopback fixture，合成样本；无企业原文、无生产数据、无真实业务流量 |
| 宿主 | Arch / Omarchy，Python 3.12.10（仓库 `.venv`），Docker 29.7.2 / Compose 5.5.1 |
| 依赖镜像 | `postgres:16.4`、`qdrant/qdrant:v1.12.4`、`redis:7.4.1`、`pgsty/silo:RELEASE.2026-09-16T00-00-00Z` |
| 隔离资源 | PG 库 `pivot_retest_20261103`、Qdrant 集合 `pivot_retest_20261103*`、Silo 桶 `pivot-retest-20261103` |
| API 装配（sync） | `PIVOT_STORAGE=postgres`、`PIVOT_VECTOR_STORE=qdrant`、`PIVOT_OBJECT_STORE=minio`、`PIVOT_CACHE_STORE=redis`、`PIVOT_QUEUE_STORE=redis`、`PIVOT_INGEST=sync`、`PIVOT_EMBEDDING=hash`、`PIVOT_LLM=local`、`PIVOT_PARSER=native` |
| API 装配（celery） | 同上，另起 8021 实例 + `PIVOT_INGEST=celery`，独立 `python -m pivot_worker` 进程消费 `retest-parse-20261103` |
| 真实模型 | `deepseek/deepseek-flash`（DeepSeek V4.1 Flash，base `https://api.deepseek.com`），密钥来自本机 pi 配置，仅环境注入，未落盘、未打印 |
| 测试账号 | `local-admin`（总管理员）、`alice`（d-tech 部门管理员）、`bob`（d-tech 编辑 + d-hr 读者）、`dave`（d-hr 部门管理员）、`erin`（d-hr 编辑）、`carol`（无部门成员）、`frank`（过期规则探针专用） |
| 测试库结构 | `d-tech`（部门库，含受限文件夹 `f-secret`）、`d-hr`（部门库）、`unassigned`（未分配库） |

## 3. 部署检查

| 检查 | 结果 |
| --- | --- |
| `docker compose up -d postgres minio qdrant redis` | 四容器启动；postgres/minio/redis healthy，**qdrant 恒为 unhealthy**（见 D8-03） |
| PostgreSQL 迁移 `alembic upgrade head` | 成功，`alembic_version=c8842fce3b98`，`public` schema 31 张表 |
| `GET /healthz` | 200 `{"status":"ok"}` |
| `GET /readyz` | 200 `{"status":"ready","checks":{"postgres":true,"minio":true,"qdrant":true,"redis":true}}` |
| Qdrant 直连 `GET /readyz` | `all shards are ready`（服务健康，仅容器探针失败） |

## 4. 回归测试结果（任务 9）

`ops/run_grouped_tests.py --skip-web`，Python 3.12.10：

| 分组 | 结果 |
| --- | --- |
| M01-auth（`tests/unit/auth` + `tests/security/auth`） | 271 passed / 44.03 s |
| M02-documents | 57 passed / 1.00 s |
| M04-retrieval | 163 passed / 19.98 s |
| M05-qa-stream | 221 passed, 22 skipped / 12.04 s |
| M06-export-audit | 37 passed / 3.61 s |
| M07-worker | 87 passed / 13.54 s |
| M00-M03-contract-db | 447 passed / 43.27 s |
| M03-db-pg-faults（无 `PIVOT_TEST_PG_URL` 时） | 50 skipped |
| M11-pipeline | 384 passed, 16 skipped / 323.60 s |
| M11-security-ops | 128 passed / 6.79 s |
| M11-performance-plan | 11 passed, 1 skipped / 0.53 s |
| ruff | `All checks passed!` |
| compileall | 通过 |
| **合计** | **1806 passed / 89 skipped / 0 failed** |

真实 PG 组单独启用（`PIVOT_TEST_PG_URL` 指向本机 maintenance 库，且**不带** `DATABASE_URL`）：

```
tests/integration/db_pg  →  50 passed in 351.91s
```

其中 04-F 故障矩阵 5 项全过：`only_one_executor_per_run`、`result_commit_kill_rolls_back`、`checkpoint_kill_before_confirm_fails_closed`、`restart_from_checkpoint`、`stale_executor_commit_rejected_after_takeover`。

## 5. 已登记缺陷复测（缺陷 1~7）

| 缺陷 | 结果 | 实测证据 |
| --- | --- | --- |
| 1 认领与跨库移动后成员检索 | **通过** | 认领前 d-tech 成员 0 命中；认领后 1 命中，且与管理员结果一致。跨库移动到 d-hr 后（`status=approved`），d-hr 读者与编辑均命中同一文档 |
| 2 查询时重建 | **通过** | 见 §6 任务 1、2、3、5、6、7、8 |
| 3 文件夹与例外读取 | **通过** | 受限文件夹：详情/版本/预览/下载 **全部 404**，`/documents` 列表 200 但不含该条目，检索不返回。例外授予后：详情 200（565 B）、版本 200（335 B）、预览 200（1467 B）、下载 200（1467 B）、列表包含 |
| 4 内容去重跨库 | **通过** | d-hr 编辑 erin（无 d-tech 权限）上传与 d-tech 文档同字节内容并指定 d-hr：**201**，新建 fork `doc_UkZJ...`，`state=pending_approval`，`target_library_id=d-hr` 正确回显，响应不含源文档 ID |
| 5 示例配置 BM25 参数 | **未通过** | 见 D8-02：Compose 未透传 `PIVOT_BM25_K1/B`，容器启动即 `RuntimeError` |
| 6 示例公开下载地址 | **无法验证** | 配置值通过 signer 校验（api 正常启动），下载链路被 D8-06 阻断 |
| 7 Silo 对象存储 | **通过** | `health/live` 200；建桶成功；上传 288 B；读取往返一致；预签下载 200（host `127.0.0.1:9000`）且字节一致 |

## 6. 缺陷 2 任务清单结果

| 任务 | 结果 | 实测 |
| --- | --- | --- |
| 1 启动后新入库免重启可见 | 通过 | 上传后 `/search` 立即命中该文档（同一进程，无重启） |
| 2 认领/移动后库归属即时生效 | 通过 | 移动后 d-hr 读者与编辑均命中，无需重启 |
| 3 删除后不再返回 | 通过 | `POST /documents/{id}/delete` 202，随后 `/search` 不含该文档 |
| 4 版本取代后旧 chunk 不返回 | **未测** | 产品无“追加新版本”HTTP 入口，见 §13 |
| 5 重启前后同一查询一致 | 通过 | 三个查询（住宿/津贴/差旅）的文档集合与顺序重启前后**完全相同**，快照见 `restart-before.json` |
| 6 BM25 腿非空、非 dense 单路 | 通过（口径受限） | 基础集合可滚动 4 条 payload；查询“住宿”：BM25 腿独立命中 1 chunk、dense 腿 4 chunk，融合后 3 条证据；两腿 `provider_calls` 均 `ok`。因 dense 无相关性下限（D8-10），`bm25_only` 为空集，**不能拿它当判据** |
| 7 重建失败降级 | 通过 | 注入滚动失败后 `status=ok`，dense 腿照常给出 4 条证据，整次检索未失败；恢复后 BM25 腿自动回到正常 |
| 8 性能 16/100/1000 chunk | 通过（下界口径） | BM25 重建中位耗时：16 → **13.21 ms**、100 → **31.38 ms**、1000 → **253.35 ms**（各 5 次采样：13.21/15.89/12.16/13.41/12.39；31.38/29.41/38.67/29.66/34.77；253.35/260.69/243.98/260.76/249.05） |
| 9 既有回归 | 通过 | 见 §4 |

任务 8 口径说明：合成 payload 写入独立 perf 集合，`version_is_live` 用恒真回调，测的是**真实 Qdrant 滚动 + BM25 重建 + 打分**的成本，**不含** PG 实时事实过滤，因此是整条链路的下界，不能当作可上生产规模的结论。

## 7. 真实依赖全链路（任务 10~12）

| 任务 | 结果 | 实测 |
| --- | --- | --- |
| 10 sync 入库后检索与问答 | 通过 | 上传即检索可见；问答 `state=answered`，消息正文包含证据原文 |
| 11 Celery 入库免重启 | 通过 | 独立 worker 进程 + `PIVOT_INGEST=celery` 的 API（8021）：上传返回 `uploaded`，worker 消费后版本转 `ready`；`/search` 命中新文档；问答 `answered`，答案包含 worker 入库的正文；**全程未重启 API** |
| 12 全链路各跑一次 | 部分 | 上传、native 解析、认领、移动、删除（202 + 检索消失）、Run 取消、API 重启均已跑；解析失败路径未构造 |

## 8. 补充验证

| 项 | 结果 | 实测 |
| --- | --- | --- |
| Run 取消幂等 | 通过 | 两次 `POST /runs/{id}/cancel` 均 200，`state=cancelled`，2 秒后终态仍为 `cancelled` |
| SSE 事件流 | 通过 | 28 条事件，事件名含 `run_started`/`stage`/`token`/`citation`/`completed` |
| 管理端任务 | 通过 | `GET /admin/tasks` 200，4 条持久化任务 |
| 管理端指标 | **未通过** | `GET /admin/metrics` 500，见 D8-11 |
| 登录失败限流 | 通过（口径更正） | 连续 6 次错口令：前 5 次审计 `denied`，第 6 次审计 `blocked`，计数到 5；HTTP 始终 401 `AUTH_INVALID_CREDENTIALS`。SPEC FR-AUTH-002 只要求“统一错误 + 触发限流”，阈值/窗口是 `TBD-P0`，故统一 401 **不算缺陷**（初版探针按 429 判失败，在此更正） |
| 成员过期/续期 | **未通过** | 见 D8-16 |

## 9. 任务 13 四项指标

模型 `deepseek/deepseek-flash`，密钥来自本机 pi 配置（仅环境注入）。

| 指标 | 实测 | 口径 |
| --- | --- | --- |
| 引用错误率 | **0.0**（5 个 answered 场景 / 7 条 claim / 0 条无绑定 / 0 条不在所引证据中）。三次独立运行分别得到 4、7、5 个 answered、claim 总数 4、10、7，**错误数恒为 0** | 生产 HTTP writer + 真实模型跑图；逐条 claim 校验“文本能否在**其绑定**的那条证据中找到”，以及“绑定证据是否属于本 Run 已注册证据”。评测装配的 `GoldenDraftWriter` 是确定性回填，不能用来测此项 |
| 过期规则命中 | **5/5** | 专用账号 frank：基线 404、带过期授予后仍 404、显式 `expires_at=null` 后 200、撤销后 404、成员过期后不可见。先清理历史残留再测，保证基线干净 |
| 租约 fencing | **5/5** | 真实 PG 故障矩阵五项（单执行者、被杀回滚、确认前被杀 fail-closed、重启恢复、接管后旧 token 被拒） |
| 预算对账 | **账本自洽，但漏记收尾器调用** | 10 个场景共 78 次调用、89,451 token；逐场景 `budget_state.model_calls` 与 attempts 数相等、token 逐 token 相等；无场景超过 10 次调用或 20k token 上限。收尾器调用不在账本（D8-13） |

Agent Golden Set（`spec/fixtures/golden-set/agent/v0.1-public.json`）逐场景：

| 场景 | 评测装配（GoldenDraftWriter） | 生产 writer 装配 |
| --- | --- | --- |
| ag-001 | 通过（7 次调用） | completed，1 claim |
| ag-002 | **失败** `budget_exhausted`（10 次） | `budget_exhausted` |
| ag-003 | 通过（10 次） | completed，2 claims |
| ag-004 | 通过（7 次） | completed，2 claims |
| ag-005 | 通过 `insufficient_evidence`（7 次） | 本次 `budget_exhausted`（历次在 insufficient / exhausted 间波动） |
| ag-006 | **失败** `budget_exhausted`（10 次） | `budget_exhausted` |
| ag-007 | 通过（4 次） | completed，1 claim |
| ag-008 | 通过（2 次） | `budget_exhausted` |
| ag-009 | 通过（9 次） | `budget_exhausted` |
| ag-010 | 通过（7 次） | completed，1 claim |
| 合计 | **8/10**，73 次调用，73,270 输入 / 8,837 输出 token，估算 $0.0163 | **5/10 answered**，10 个场景 78 次调用、89,451 token |

评测装配的失败项与 PROGRESS 已登记形态一致（“证据无法满足模型时在决策循环内耗尽预算，走不到收尾”）。生产 writer 装配的通过率下降原因**尚未定性**，列入待定性观察（D8-13 相关）。

## 10. 问题清单

### D8-01 重复用户名创建用户返回 500，且日志打印口令哈希

- 级别：P1。状态：新发现，未修复。
- 现象：`POST /api/v1/admin/users` 用已存在的 `username` 再次创建 → `500 Internal Server Error`，响应体不是 §5.1 错误包（无 `code`、无 `request_id`）。
- 复现：先建 `dup-probe` 得 201，再建同名得 500。
- 服务端日志同时打印完整 SQL 与参数，其中含 `password_hash`（argon2id）与用户名。
- 初步定位（只指出位置，未改）：`api/src/pivot/auth/service.py:171 create_user` 无唯一性预检；`api/src/pivot/auth/directory.py:43 SqlAlchemyUserDirectory.save` 直接 INSERT，`UniqueViolation` 逃逸到 FastAPI 默认处理器。
- 影响：管理员建号重试不可用；违反 SPEC §5.1（错误包、不返回堆栈）；口令哈希入日志违反 FR-AUDIT-002 脱敏要求。SQLite 路径同样会触发唯一约束，非 PG 特例。

### D8-02 示例配置的 api 容器没有拿到 BM25 参数，启动即失败（缺陷 5 未闭合）

- 级别：P1。状态：新发现，未修复。
- 现象：`ops/compose.env.example` 已有 `PIVOT_BM25_K1=1.2`、`PIVOT_BM25_B=0.75`，但 `docker-compose.yml` 的 `api` 服务 `environment:` 块没有透传这两个键，容器内看不到它们。
- 证据：`docker compose --profile app config` 渲染出的 `api`/`worker` 环境变量中**无任何 `PIVOT_BM25_*`**；用容器可见变量装配抛
  `RuntimeError: PIVOT_BM25_K1 and PIVOT_BM25_B are required when PIVOT_RETRIEVAL_BACKEND=llama`。
- 影响：按示例配置启动 app profile，api 直接启动失败。缺陷 5 的修复只做在示例文件，未做 Compose 透传。

### D8-03 qdrant 健康检查依赖 wget，镜像内不存在，容器永久 unhealthy

- 级别：P1（阻断部署）。状态：新发现，未修复。
- 现象：`docker-compose.yml` 的 qdrant 健康检查为 `wget -qO- http://127.0.0.1:6333/readyz`；`qdrant/qdrant:v1.12.4` 内既无 `wget` 也无 `curl`。
- 证据：健康日志连续 `ExitCode 1` / `/bin/sh: 1: wget: not found`；`docker inspect` 状态 `unhealthy`；容器内 `command -v wget`/`curl` 均 `not found`；但 `GET /readyz` 实际返回 `all shards are ready`。
- 影响：`api`、`worker` 都 `depends_on: qdrant: condition: service_healthy`，因此 **app profile 永远起不来**。

### D8-04 示例配置的 web 反代指向容器自身

- 级别：P2。状态：新发现，未修复。
- 现象：`PIVOT_API_ORIGIN=http://127.0.0.1:8000`。在 web 容器内 `127.0.0.1` 是它自己，api 的服务名是 `api`。
- 证据：`docker compose --profile app config` 渲染 `web.PIVOT_API_ORIGIN = http://127.0.0.1:8000`；compose 注释本身写明 app profile 应注入 `http://api:8000`。
- 影响：按示例启动后 web 的 `/api/v1` 反代打回自身，前台不可用。

### D8-05 bucket 与 collection 缺创建路径，且报错信息误导

- 级别：P2。状态：新发现，未修复。
- 现象：示例未启用 `PIVOT_MINIO_ENSURE_BUCKET`，`PIVOT_QDRANT_ENSURE_COLLECTION` 在示例里是注释；两者缺失时分别报 `minio is not reachable`、`qdrant is not reachable`，而服务其实健康。
- 证据：同一份示例变量下依次得到 `RuntimeError: minio is not reachable`（Silo 健康、仅 `pivot-docs` 桶不存在，手工建桶后变下一个错）→ `RuntimeError: qdrant is not reachable`（Qdrant 健康、仅集合 `pivot` 不存在）。
- 影响：`healthy()` 的实际语义是“桶/集合存在”，却报成“服务不可达”，排障方向被带偏；新环境按文档起步会在两处反复卡住。

### D8-06 导出功能在真实 PG 装配下不可用（两个来源各自失效）

- 级别：P1。状态：新发现，未修复。
- 现象一（会话导出恒失败）：`POST /exports`（`source_type=conversation`）202，随后 `GET /exports/{id}` 恒为 `state=failed`、`download_url=null`。
- 现象二（文档导出恒 404）：`POST /exports`（`source_type=document`，管理员对已入库文档）返回 `404 RESOURCE_NOT_FOUND`。
- 初步定位（只指出位置，未改）：
  - `api/src/pivot/exports/service.py:188 _load_payload` 要求 `answers.get_exportable_answer()` 返回 `EXPORTABLE_RUN_STATES` 内的 `PersistedAnswer`；**生产代码从未构造 `PersistedAnswer`**（全仓仅测试构造）。
  - 文档源走 `MemoryExportAccess.authorize_document` → `resources.get_document()`；PG 装配下文档事实在 SQLAlchemy 行里，`_LibraryBackedCatalog`（`bootstrap.py:158`）没有代理 `get_document`，内存目录为空，于是判 404。
- 影响：FR-EXPORT-001/002/003 在真实装配下不可用；缺陷 6 因此无法端到端验证。

### D8-07 导出失败静默，用户与运维都拿不到原因

- 级别：P2。状态：新发现，未修复。
- 现象：失败分支只置 `error_code="EXPORT_FAILED"` 并写审计，不打日志；`GET /exports/{id}` 视图不含 `error_code`。
- 证据：响应只有 `{"export_id", "state":"failed", "download_url":null, "expires_at"}`；api 日志无异常记录；审计表 `export.create|ok|2`、`export.failed|failed|2`。
- 影响：只能查库才知道失败原因；FR-EXPORT-003 的可观测性不足。

### D8-08 跨库移动批准后 `reconcile_status` 仍为 pending

- 级别：P2。状态：旧“观测 1”残留，未闭合。
- 现象：移动请求 `status=approved` 后，`reconcile_status` 仍为 `pending`、`reconcile_attempts=0`。
- 证据：`{"move_status": "approved", "reconcile_status": "pending"}`。
- 影响：调和状态不推进，“已调和”无法作为运维判据；不影响本轮检索可见性（缺陷 1 修复后按实时事实回填）。

### D8-09 `db_pg` 组对环境变量 `DATABASE_URL` 敏感，可能静默打到错误的库

- 级别：P3（测试工程）。状态：新发现，未修复。
- 现象：`migrations/env.py` 优先取 `DATABASE_URL`，覆盖 `tests/integration/db_pg/conftest.py` 设置的 `sqlalchemy.url`。若运行环境存在该变量，建库与迁移分别打到两个库，测试库无表，**50 项全部失败**，报错为 `relation "users" does not exist`。
- 证据：第一次运行 50 failed（环境带着迁移用的 `DATABASE_URL`）；去掉后 50 passed。
- 影响：真实 PG 组结果对调用环境敏感，容易把测试环境问题误判为产品缺陷。

### D8-10 `/search` 无相关性下限，结果与问题无关

- 级别：P2（能力缺口，已定性）。状态：已知，属 DR-010 待冻结范围。
- 现象：查询“住宿”返回 3 篇文档，其中 2 篇正文不含“住宿”；`PIVOT_EMBEDDING=hash` 下 dense 腿对任何查询都返回全库候选。
- 证据：`{"query": "住宿", "bm25_leg_hits": 1, "dense_leg_hits": 4}`。
- 影响：搜索结果页会给出不相关文档；线三相关性门禁默认关闭、候选值随 DR-010 冻结。不作为新缺陷，仅登记为复测口径风险。

### D8-11 `GET /admin/metrics` 在库中有文档时 500

- 级别：P1。状态：新发现，未修复。
- 现象：`GET /api/v1/admin/metrics` → 500，响应体不是结构化错误包。同一次调用中 `/admin/tasks` 200、4 条任务。
- 证据：异常 `AttributeError: 'DocumentRecord' object has no attribute 'status'`，位置 `api/src/pivot/documents/service.py:75 count_indexed`；同文件 `count_pending`、`count_failed` 同样读 `doc.status`。而 `api/src/pivot/documents/ports.py:11 DocumentRecord` 没有 `status` 字段，状态实际在 `VersionRecord.state`。
- 复现要点：`sum(...)` 遍历空列表时不访问属性，因此**空库下接口正常**，只有存在文档时才崩——这解释了 CI 绿灯与真实库 500 的差异。
- 影响：管理后台指标页不可用；ND-GAP-01 记录过“修复状态字段误读的潜伏崩溃”，本处仍在。

### D8-12 `PIVOT_REDIS_DB` 与 endpoint 路径同时存在时静默失效

- 级别：P3。状态：新发现，未修复。
- 现象：`PIVOT_REDIS_ENDPOINT=redis://127.0.0.1:6379/0` 且 `PIVOT_REDIS_DB=8` 时，缓存写入落在 **db 0**，`PIVOT_REDIS_DB` 被静默忽略。
- 证据：`connect_redis_client(endpoint='redis://127.0.0.1:6379/0', db=8)` 后写入的键只出现在 db 0；登录尝试计数器落 db 0，而 Celery broker（显式 `/8`）在 db 8。
- 影响：两个配置源表达同一含义却无校验、无告警，排障时容易误判“限流没走 Redis”。

### D8-13 收尾器（Draft Writer）的模型调用不计入 Run 预算账本

- 级别：P2。状态：新发现，未修复。
- 现象：规划器调用都登记在 `budget_state`（`model_calls`、`total_tokens`），但结构化收尾时由 `HttpDraftWriter` 发出的那次真实模型调用**既不进 attempts 账本，也不进 `budget_state`**。
- 证据：`ag-001` 在 HTTP writer 装配下 `attempts=9`、`budget_state.model_calls=9`、`total_tokens=10969` 与账本逐 token 相等；但该 Run 除 9 次规划调用外至少还多 1 次 writer 调用（否则不会产出 claims）。
- 影响：AGENT_SPEC §6 要求“所有模型与工具调用前检查预算、返回后登记实际用量”，收尾器未纳入；DR-010 的费用上限核算与“单 Run 调用中位数”会系统性偏低。

### D8-14 两套模型配置的 endpoint 语义不同，且同名易混

- 级别：P3。状态：新发现，未修复（配置口径问题）。
- 现象：`PIVOT_LLM_ENDPOINT` 必须是**完整 completions 路径**（`https://api.deepseek.com/v1/chat/completions`）；`PIVOT_AGENT_MODEL_ENDPOINT` 是 **base URL**（`https://api.deepseek.com/v1`，由 ChatOpenAI 拼路径）。
- 证据：把 base URL 填给 `PIVOT_LLM_ENDPOINT` 时 10 个场景全部 `WriterError: provider rejected request`；改成完整路径后正常产出 claims。
- 影响：新环境按名字直觉填写必然踩坑，错误信息也不指向配置项。

### D8-15（已解释，降级）曾观察到一次跨部门非成员读取 200

- 级别：已降级为观察，不计缺陷。
- 经过：`dave`（仅 d-hr）在某一时刻读取 d-tech 受限文件夹文档返回 200，随后同账号同文档重测稳定 404。
- 结论：干净状态下的 5 项矩阵（基线 404、过期例外 404、永久例外 200、撤销后 404、成员过期不可见）**全部正确**；那次 200 最可能由我前序探针残留的例外行导致（同一账号上确实存在过手工授予的行）。留档备查，不再按越权处理。

### D8-16 成员设成已过期后行被清理，续期返回 404，成员关系静默消失

- 级别：P1。状态：新发现，可稳定复现，未修复。
- 现象：把部门成员的 `expires_at` 改成过去时间（或原授权自然到期），成员行会被懒清理删除；随后 `PATCH /admin/departments/{dept}/members/{user_id}` 续期（`expires_at=null` 或未来时间）返回 **404 `RESOURCE_NOT_FOUND`**，该成员关系从库中消失，其可见文档一并归零。
- 复现（本轮实测）：`frank` 加入 `d-tech` reader → PATCH 到期时间 2027 → PATCH 到期时间 2020 → PATCH `expires_at=null` → 200、200、**404**；随后 `select ... from memberships where user_id=frank` 无行。同样现象在 `erin`（d-hr editor）上出现：其成员行已从库中消失，检索可见文档数归 0。
- 初步定位（只指出位置，未改）：P1-2 S2 的“读取时过期判定 + 过期行懒清理”与“续期走角色变更路径”在实现上冲突——清理先删除行，续期路径随后按 `(user_id, dept_id)` 找不到行而 404。
- 影响：临时授权到期后成员被静默移除，管理员无法续期，只能重新添加；审计上表现为“成员消失”，续期链路失效。属于权限生命周期缺陷。

## 11. 环境事件

- E1 **Docker daemon 整体重启**：四个依赖容器同一时刻 `exit 255`（`docker ps -a` 显示同一时间点退出）。已全部拉起恢复，非产品缺陷。期间一次 API 启动因依赖未起而失败，属该事件连带。
- E2 首次 `db_pg` 运行 50 项失败由 D8-09 引起，属测试环境问题，非产品缺陷。
- E3 Docker Hub 直连可通（daemon 已配 `127.0.0.1:7897` 代理、Clash 在监听），`python:3.12.10-slim-bookworm` 已成功拉取，**构建不再是阻断项**。

## 12. 未测项与口径限制

- **任务 4（版本取代）**：无 HTTP 入口，改为需求提案，见 §13。
- **任务 12 的解析失败路径**：未构造损坏/加密/超大样本，`FR-DOC-004` 错误码分支本轮未覆盖。
- **缺陷 5、6 的 app profile 端到端**：未构建镜像（D8-02、D8-03 已足以证明该路径不可用），改用同参数在宿主进程装配验证。
- **任务 13**：引用错误率是脚本口径（子串 + 关键 token 命中），未做人工语义判定；未跑 thinking 开关两组对照；未做多轮重复取中位数。
- **任务 8 性能**：只测 BM25 重建下界，未测含 PG 事实过滤的整链耗时，也未测 `/search` 端到端 P50/P95。
- **web 侧**：`npm test` / `typecheck` / `lint` / Playwright 十页本轮未跑（使用了 `--skip-web`）。
- **Agent 装配差异**：评测装配与生产 writer 装配通过率差异（8/10 vs 5/10）原因未定性。

## 13. 任务 4 需求规格：文档版本追加与取代（`FR-DOC-009`）

任务 4 要验证“版本取代后旧版本 chunk 不再返回”，但当前产品没有给既有文档追加新版本的 HTTP 入口：`POST /documents` 每次新建文档，同字节命中内容去重时新建 fork，改库走 `/moves`。因此该任务无法从接口复测，只能靠单测（`test_local_real_deps_20261103_bm25_live_rebuild.py` 覆盖 `version_is_live` 翻转后的丢弃），不能替代真实依赖复测。

**需求 ID（建议）**：`FR-DOC-009` 文档版本追加与取代。Accountable：M02 文档接入；Contributor：M04（检索切换验证）、M07（索引对账）。

**接口**：`POST /api/v1/documents/{document_id}/versions`，`multipart/form-data`。

| 字段 | 必填 | 规则 |
| --- | --- | --- |
| `file` | 是 | 白名单扩展名 + 声明 MIME + 文件魔数三者一致（FR-DOC-001/002） |
| `title` | 否 | 缺省沿用当前文档标题 |
| `Idempotency-Key` | 否 | 同一 key 重复提交返回同一版本，不新建（FR-DOC-005） |

**前置校验（全部 fail-closed）**：

1. 文档存在且未删除，否则 404 `RESOURCE_NOT_FOUND`；
2. 上传者在该文档所属库（或所属文件夹）具备编辑及以上权限，纯读者与无成员拒绝，复用 P1-2 S5 上传门禁；
3. 不允许借追加版本迁库，库与文件夹归属不变，迁库仍走 `/moves`；
4. 文档存在未决发布审批请求时的行为必须显式定义（建议：拒绝并返回 409，避免两套未决请求并存）。

**行为**：

- 新版本以 `uploaded` 落库，按 `PIVOT_INGEST` 同步或入队；响应 202（异步）或 201（同步完成），返回 `{document_id, version_id, state, current}`；
- 只有新版本完成对象保存、解析、分块、嵌入、索引与抽样校验后才置 `current=true`，旧版本在同一事务内转 `current=false`（FR-DOC-006 原子发布）；
- 新版本失败时旧版本保持 `current=true` 且继续可检索、可下载，失败版本按 FR-DOC-004 带错误码；
- 上传者不是该库审批人时，新版本进入 `pending_approval`，**旧版本保持对外可用**，审批通过后再切换（与 P1-3 一致）；
- 审计新增 `doc.version.created`（含 `version_id`、父版本、操作者、结果）。

**取代语义（任务 4 的断言基础）**：

- 新版本 `ready` 后，检索、详情、预览、下载、引用、导出只返回 `current` 版本；
- 旧版本 chunk 必须从 `/search` 与问答证据中消失，不能因基础集合不清理而残留（与缺陷 2 的实时事实过滤同一机制）；
- `/documents/{id}/versions` 同时返回新旧两版，且只有一版 `current=true`；
- 旧版本原始对象保留，清理策略随删除/保留期统一处理，不单独定义。

**测试 ID（建议）**：`test_FR_DOC_009_http_append_version_success`、`_permission_denied`、`_idempotent_replay`、`_failure_keeps_old_current`、`_search_drops_old_chunk`、`_approval_branch`。

**验收**：真实依赖下追加新版本后，`/search` 不再返回旧 chunk、`/versions` 显示两版且 `current` 唯一；失败路径下旧版本仍可检索。

**未决（`TBD-P0`）**：单文档版本数上限、旧版本保留期、是否允许同名覆盖、并发追加同一文档的串行化策略（沿用 FR-STREAM-001 的幂等/唯一约束口径）。

**替代方案（若不做该入口）**：只能接受“服务级真实依赖复测”——测试脚本直接写新版本行、触发 ingest 后翻 `current`，验证检索侧切换。这能证明检索行为，但**不能证明产品链路**，需在任务清单注明该限制。

## 14. 复现方式与证据索引

### 14.1 环境重建

```bash
cd /home/lumina888/Projects/Pivot
docker compose --env-file ops/compose.env.example up -d postgres minio qdrant redis
.venv/bin/python .pi/artifacts/integration-retest-20261103/reset_state.py   # 重建隔离库/集合/桶
# 启动被测 API（bash 侧读 .env.real-deps，测试专用 env 由 support.py 生成）
```

### 14.2 复测脚本（均在 `.pi/artifacts/integration-retest-20261103/`）

| 脚本 | 覆盖 | 产物 |
| --- | --- | --- |
| `reset_state.py` | 重建 PG 库 + 迁移 + 清空 Qdrant 集合与 Silo 桶 | 控制台 |
| `e2e_http.py` | 缺陷 1/3/4、缺陷 2 任务 1/2/3 | `results-http.json` |
| `inprocess_probe.py` | 缺陷 2 任务 6/7/8（真实 Qdrant，进程内） | `results-bm25.json` |
| `silo_probe.py` | 缺陷 7 四步 | `results-silo.json` |
| `lifecycle_probe.py restart-before|restart-compare` | 缺陷 2 任务 5 | `restart-*.json` |
| `lifecycle_probe.py sync-qa|celery` | 任务 10/11（含独立 worker 进程） | 控制台 |
| `extras_probe.py` | Run 取消、SSE、管理端、登录限流 | `results-extra.json` |
| `task13_probe.py all` | 引用错误率、预算对账、过期规则 | `results-task13.json` |
| `run_live_eval.py` | Agent Golden Set（真实模型） | `agent-live-eval.json` |
| `citation_diag.py` | 单场景 claim↔证据逐条比对（诊断用） | 控制台 |

### 14.3 运行日志

`regression.log`（分组回归）、`postgres-tests.log`（真实 PG）、`api.log`（被测 API）、`api-celery.log`、`worker.log`、`migration.log`。

## 15. 变更记录

| 版本 | 时间 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-11-04 | 建立清单：缺陷 1/2/3/4/7 复测通过；新增 D8-01~D8-10；记录部署检查与任务 1~11 实测 |
| v0.2 | 2026-11-04 | 真实 PG 组 50 passed；新增 D8-11（指标 500）、D8-12（Redis 库号双来源）；补取消/SSE/任务/限流并更正限流口径 |
| v0.3 | 2026-11-04 | 用 deepseek-flash 实跑 Golden Set 与任务 13；新增 D8-13（writer 不进账本）、D8-14（endpoint 语义）、D8-15（越权观察）；补任务 4 需求 |
| v1.0 | 2026-11-04 | 汇总为完整报告：补全分组回归明细、部署检查、逐任务数字与性能采样；D8-15 降级为已解释观察；新增 D8-16（成员过期后续期 404、成员关系静默消失，可稳定复现）；任务 13 三项指标用干净矩阵重测（过期规则 5/5）；补复现方式与证据索引 |

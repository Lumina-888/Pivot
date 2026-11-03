# 2026-11-03 本机真实依赖联调证据

## 范围与授权

- 输入基线 `main` `0587a73`。联调在本机工作区 `/home/lumina888/Projects/Pivot` 执行。
- Owner 要求在本机做真实依赖联调，验证系统可用性；不租用云主机，不做 staging 部署。
- 本轮只覆盖本机 loopback fixture。结论不等于 staging、生产或 GATE 验收，`GATE-P0-001~008` 仍全部 unverified。
- 未修改业务源码、公开契约、迁移、依赖锁与 `TBD-P0`。仓库内改动只有 `.gitignore` 追加本地 SQLite 忽略规则。
- 私密配置写入 gitignored 的 `.env.real-deps`；登录口令与本文件无关，不写入。

## 环境

| 项目 | 版本 |
| --- | --- |
| 系统 | Arch/Omarchy x86_64，Linux 7.2.5-3-omarchy |
| Python | 3.12.10（仓库 `.venv`） |
| pytest | 9.1.1 |
| Docker | client/server 29.7.2 |
| Docker Compose | 5.5.1 |
| PostgreSQL 镜像 | `postgres:16.4` |
| Qdrant 镜像 | `qdrant/qdrant:v1.12.4` |
| Redis 镜像 | `redis:7.4.1` |

Docker daemon 原无代理配置，直连 Docker Hub 超时。本机 Clash 监听 `127.0.0.1:7897`，`curl -x` 访问 `registry-1.docker.io` 返回 401，说明代理链路可用。按仓库既有脚本新增 systemd drop-in 后 daemon 生效：

```bash
pkexec /usr/bin/bash "$PWD/.pi/artifacts/local-linux-20261003/configure-docker-proxy.sh"
```

脚本只新增 `/etc/systemd/system/docker.service.d/pivot-proxy.conf`（`HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY`），执行 `systemctl daemon-reload` 与重启 docker，未改 `/etc/docker/daemon.json`。

## 回归基线

联调前在 `0587a73` 上跑过的三组检查：

| 检查 | 结果 |
| --- | --- |
| `pytest -q tests/unit/auth tests/security/auth` | 271 passed（43.05 秒） |
| `pytest -q tests/integration/pipeline` | 380 passed，20 skipped（312.18 秒） |
| `npm --prefix web test` | 18 passed |

首次收集 pipeline 时两个模块 ImportError：`.venv` 缺 `llama-index-vector-stores-qdrant==0.3.3`。该包在 `api/pyproject.toml` 主依赖中，属本机环境漂移；补装后全绿，未改仓库依赖声明。

## 启动真实依赖

```bash
docker compose --env-file ops/compose.env.example pull postgres qdrant redis
docker compose --env-file ops/compose.env.example up -d postgres qdrant redis
```

| 容器 | 端口 | 健康 |
| --- | --- | --- |
| `pivot-deps-postgres-1` | `127.0.0.1:5432` | accepting connections |
| `pivot-deps-qdrant-1` | `127.0.0.1:6333` | `all shards are ready` |
| `pivot-deps-redis-1` | `127.0.0.1:6379` | `PONG` |

`minio` 未启动，原因见缺陷 7。

## 真实 PostgreSQL 迁移

```bash
DATABASE_URL="postgresql+psycopg://pivot:pivot_dev_only@127.0.0.1:5432/pivot" \
  .venv/bin/python -m alembic -c migrations/alembic.ini upgrade head
```

12 个迁移全部执行成功，`alembic_version` 为单头 `c8842fce3b98`，`public` schema 共 31 张表。抽查关键表存在：`libraries`、`folders`、`folder_memberships`、`memberships`、`document_exceptions`、`approval_requests`、`move_requests`、`run_leases`、`provider_attempts`、`result_commits`。

这是真实 PG 上的首次全链迁移验证。P1-1 至 P1-3 的迁移链在 PostgreSQL 16.4 上顺序落地，未出现历史上「迁移半途静默提交」的缺陷形态。

## 启动 API

```bash
set -a && . ./.env.real-deps && set +a
.venv/bin/python -m uvicorn pivot.http.main:app --factory --host 127.0.0.1 --port 8010
```

装配选择：`PIVOT_STORAGE=postgres`、`PIVOT_VECTOR_STORE=qdrant`、`PIVOT_CACHE_STORE=redis`、`PIVOT_QUEUE_STORE=redis`、`PIVOT_INGEST=sync`、`PIVOT_EMBEDDING=hash`、`PIVOT_LLM=local`、`PIVOT_PARSER=native`、`PIVOT_OBJECT_STORE=memory`。

| 探针 | 结果 |
| --- | --- |
| `GET /healthz` | `{"status":"ok"}` |
| `GET /readyz` | `postgres` true、`qdrant` true、`redis` true、`minio` false |

`minio` 为 false 是预期：对象存储临时走 memory，见缺陷 7。

## 覆盖矩阵

测试主体：`local-admin`（总管理员）、`alice`（`d-tech` 部门管理员兼 `p-alpha` 负责人）、`bob`（`d-tech` 编辑、`d-hr` 读者、`p-beta` 负责人）、`dave`（`d-hr` 部门管理员）、`erin`（`d-hr` 编辑、项目成员）、`carol`（无部门成员）。

### A 基础链路

| 编号 | 场景 | 结果 |
| --- | --- | --- |
| A1 | 登录、access token、refresh Cookie | 通过 |
| A2 | 建用户，首登返回 `must_change_password: true` | 通过 |
| A3 | 改密前访问受保护接口 | 403 `AUTH_PASSWORD_CHANGE_REQUIRED`（符合预期） |
| A4 | 改密后重新登录 | 通过 |
| A5 | 建部门 `d-tech`、`d-hr` | 通过 |
| A6 | 部门成员授权（`dept_admin`、`editor`、`reader`） | 通过 |
| A7 | 上传 PDF → 解析 → 分块 → 嵌入 → 建集合 | 通过，`ready` |
| A8 | 文档列表、详情、版本列表 | 通过 |
| A9 | 预览、下载 | 通过（960 字节 PDF 往返一致） |
| A10 | 认领 unassigned → 部门库 | 通过，库归属更新 |
| A11 | 检索（管理员） | 通过 |
| A12 | 并发 5 个上传 | 全部 201，全部 `ready` |
| A13 | 并发 10 次检索 | 全部 200 |

### B 发布审批（P1-3 S2、S3）

| 编号 | 场景 | 结果 |
| --- | --- | --- |
| B1 | 编辑上传到部门库（非审批人） | 201，`pending_approval`，建请求，零 ingest |
| B2 | 提议人查待办队列 | 200，含自己提交项与 `document_title` |
| B3 | 目标库管理员查待办队列 | 200，含该项 |
| B4 | 其他部门管理员查待办 | 200，空 |
| B5 | 待批文档在 `/documents` 列表 | 不可见（符合 fail-closed） |
| B6 | 待批态复核读（提议人） | 200，返回隔离存储 PDF 字节 |
| B7 | 提议人自批 | 403 `AUTH_FORBIDDEN` |
| B8 | 他部门管理员批准 | 404 `RESOURCE_NOT_FOUND` |
| B9 | 与本请求无关用户批准 | 404 `RESOURCE_NOT_FOUND` |
| B10 | 本部门管理员批准 | 200，版本转 `ready`，库归属生效 |
| B11 | 批准后成员检索 | 命中（该路径 payload 正确） |
| B12 | 已决后复核读 | 403 `RESOURCE_FORBIDDEN`（文档口径写 `illegal_state`，见观测 3） |
| B13 | 部门管理员自批直通 | 201，`uploaded`，请求 `approved`，成员可检索 |

### C 拒绝、撤回、重提、改目标

| 编号 | 场景 | 结果 |
| --- | --- | --- |
| C1 | 审批人拒绝（带理由） | 200，版本 `rejected`，库仍 `unassigned` |
| C2 | 驳回文档在成员列表 | 不可见 |
| C3 | 提议人重提（换目标库） | 200，状态回 `pending`，目标改 `d-hr`，理由清空 |
| C4 | 原审批人决策（目标已变） | 404 |
| C5 | 新审批人决策 | 200，落 `d-hr` |
| C6 | 提议人撤回 | 200，版本回 `uploaded` 并转 `ready` |
| C7 | 非提议人撤回 | 403 `AUTH_FORBIDDEN` |
| C8 | 撤回后文档可见性 | 成员不可见（仍在 `unassigned`），管理员可见 |
| C9 | 提议人改目标（目标是本人非成员库） | 404（目标校验按上传同规则，见观测 2） |
| C10 | 同上，先把提议人加为目标部门读者 | 200，目标改写成功 |
| C11 | 已决请求再改目标 | 403 `RESOURCE_FORBIDDEN` |

### D 跨库移动（P1-3 S4）

| 编号 | 场景 | 结果 |
| --- | --- | --- |
| D1 | 提议人非目标库成员时提议移动 | 404（见观测 2） |
| D2 | 同上，先加入目标部门 | 200，建移动请求 |
| D3 | 同一文档第二个未决移动请求 | 403 `RESOURCE_FORBIDDEN` |
| D4 | 提议人自批 | 403 `AUTH_FORBIDDEN` |
| D5 | 目标库无关者批准 | 404 |
| D6 | 目标库管理员待办队列 | 200，含源库→目标库与 `reconcile_status` |
| D7 | 目标库管理员批准 | 200，`documents.library_id` 生效，`folder_id` 置空 |
| D8 | 移动后 `reconcile_status` | 仍为 `pending`，`attempts=0`（既有残留，见观测 1） |
| D9 | 移动后目标库成员检索该文档 | **未命中**（缺陷 1） |
| D10 | 移动后无权限用户检索 | 0 命中（未见泄漏） |

### E 文档例外与文件夹

| 编号 | 场景 | 结果 |
| --- | --- | --- |
| E1 | 授予前无关用户读详情 | 404 |
| E2 | 部门管理员授个人例外（60 天） | 201 |
| E3 | 例外生效后检索 | **命中** |
| E4 | 例外生效后详情、版本、预览、下载、列表 | **全部 404**（缺陷 3） |
| E5 | 例外清单查询 | 200 |
| E6 | 撤销例外（`DELETE .../exceptions/{id}`） | 204，撤销后检索 0 命中 |
| E7 | 建部门文件夹并移入文档 | 201 / 200，`folder_id` 生效 |
| E8 | 非文件夹成员的部门成员读详情、预览、下载、列表 | **全部 200**（缺陷 3） |
| E9 | 非文件夹成员检索该文档 | 未命中（检索侧过滤生效） |
| E10 | 删除非空文件夹 | 403 `RESOURCE_FORBIDDEN` |
| E11 | 文件夹集合命名 | `pivot_local__llama__d-tech__f-2026` 已建 |

### F 项目库（P1-4）

| 编号 | 场景 | 结果 |
| --- | --- | --- |
| F1 | 建项目库并任命负责人 | 201 |
| F2 | 负责人加项目成员（60 天） | 201 |
| F3 | 纯项目负责人授 61 天 | 422 `GRANT_EXPIRY_INVALID` |
| F4 | 纯项目负责人授永久 | 422 `GRANT_EXPIRY_INVALID` |
| F5 | 纯项目负责人授 60 天 | 201 |
| F6 | 负责人任命其他负责人 | 403 |
| F7 | 牵头部门管理员（兼负责人）授 61 天与永久 | 均成功（按 ADR-017 Q1 不受限，见观测 4） |
| F8 | 项目内建文件夹 | 201 |
| F9 | 项目成员上传到项目库（非审批人） | 路径可达，审批人可批 |

### G 删除、取消、重启

| 编号 | 场景 | 结果 |
| --- | --- | --- |
| G1 | 有未决发布请求时删除文档 | 202 |
| G2 | 删除后请求状态 | `cancelled` |
| G3 | 删除后审批人决策 | 403 `RESOURCE_FORBIDDEN`（文档口径写 `not_found`，见观测 3） |
| G4 | 删除后成员/管理员可见性 | 成员 404，管理员 200 |
| G5 | 审计事件 | `doc.approval.requested`、`doc.approval.cancelled`、`authz.approval.*`、`doc.approval.retargeted` 均落库 |
| G6 | API 重启后事实保持 | 文档、版本、审计、审批请求、移动请求均保持 |
| G7 | 重启后检索 | 正常，缺陷 1 现象复现 |

## 发现的问题

### 缺陷 1：认领与移动后，目标库成员检索不到文档

严重度：功能性。上传并入库的文档在认领或移动之后，目标库成员搜不到，管理员能搜到。用户可见后果是「同事看不到已经入库的文档」。

#### 复现（认领路径）

```bash
# 1) 管理员上传，不指定目标库，等待 ingest 完成
curl -X POST $API/api/v1/documents -H "$ADMIN" \
  -F "title=差旅制度2026" -F "file=@/tmp/pivot-travel.pdf;type=application/pdf"
# 2) 部门成员检索：0 命中（正确，文档仍在 unassigned）
# 3) 部门管理员认领
curl -X POST $API/api/v1/admin/documents/$DOC/claim -H "$ADMIN" \
  -H "Content-Type: application/json" -d '{"library_id":"d-tech"}'
# 4) 部门成员再次检索：0 命中（错误，预期 1 命中）
# 5) 管理员检索：命中（无库过滤）
```

移动路径同样复现：把 `报销制度B` 从 `d-tech` 移到 `d-hr` 后，`d-hr` 编辑检索不到该文档，管理员能检索到。

#### 证据

同一时刻 Qdrant 三个集合的 payload：

| 集合 | 该文档点数 | `payload.library_id` |
| --- | --- | --- |
| `pivot_local`（基础集合） | 1 | `d-tech`（陈旧，文档已移到 `d-hr`） |
| `pivot_local__llama__d-tech` | 0 | — |
| `pivot_local__llama__d-hr` | 1 | `d-hr`（正确） |

检索侧把命中 chunk 解析成记录时取到陈旧字段：

```
chk_J9ibrkTg5F -> ('unassigned', 'doc_KCtGT3Kx')
chk_wZ7HidOApe -> ('unassigned', 'doc_KCtGT3Kx')
chk_nwKZNA8_Lz -> ('unassigned', 'doc_eDdYRofT')
```

同一 principal 的两次对照查询，过滤结果由该字段决定：

| `library_ids` | 命中数 |
| --- | --- |
| `("unassigned",)` | 1 |
| `("d-tech",)` | 0 |

#### 根因

`GET /api/v1/search` 与 QA 链路读的不是同一套集合：

| 链路 | retriever | 集合 |
| --- | --- | --- |
| `/api/v1/search` | `pivot.retrieval.vector.VectorStoreRetriever` | 基础集合 `pivot_local` |
| QA（`qa_retriever`） | `LlamaIndexRetriever` | `pivot_local__llama__<库>` |

三个环节叠加：

- 认领与移动的调和只更新按库的 llama 集合，基础集合 payload 保持旧库值。
- `/search` 的 dense 腿直接读基础集合，构建 `ChunkRecord` 时以 payload 的 `library_id` 为准，未按实时事实回填。
- `passes_filters()` 用该字段与调用者可见库集合比对，把合法命中判为越权并丢弃。

单看任一处都不会表现为「成员搜不到」。

#### 影响范围

- 上传时直接选定目标库（审批通过或自批）不受影响：ingest 发生在库归属确定之后，payload 一开始就是对的。已实测通过。
- 影响认领（P1-1、P1-2 S5）与跨库移动（P1-3 S4），两者共用同一调和入口。
- 不构成越权泄漏：过滤方向是「拒绝过多」，不是「放行过多」。

### 缺陷 2：`/search` 的 BM25 腿一直是空索引

严重度：功能性（检索质量）。装配时 `Bm25Retriever` 收到空 `corpus`，`add()` 只在 llama 检索器内部被调用，`/search` 的实例装配后从未填充：

```
bm25 索引文档数: 0
```

后果是 `/search` 实际只有 dense 单腿，RRF 融合退化为单路排序。这与已修复的 FR-RAG-009 是同类形态、方向相反：那次是 dense 静默失效、退化为 BM25 单腿，这次是 BM25 恒空、退化为 dense 单腿。文档搜索名义上是 dense + BM25 双路，实测不是。

### 缺陷 3：文档读取入口只用库可见性，文件夹限制与文档例外都不生效

严重度：访问控制口径不一致。文档读取路由把 `visible_libraries` 直接传给服务层，未经过带文件夹与例外通道的授权判定。

| 入口 | 判定依据 | 文件夹限制 | 文档例外 |
| --- | --- | --- | --- |
| `/documents`、`/documents/{id}`、`/versions`、`/preview`、`/download` | `DocumentService._visible_document`，只比 `library_id in visible_libraries` | 不生效 | 不生效 |
| `/search` | `passes_filters`，含库、文件夹与例外三类过滤 | 生效 | 生效 |
| 导出、引用、chunk 授权 | `AccessControl.authorize_document`，含文件夹与例外通道 | 生效 | 生效 |

实测两组：

- 例外：给无部门成员授予某文档的个人例外后，检索命中该文档，但详情、版本、预览、下载、列表全部 404。
- 文件夹：部门成员不在受限文件夹成员内时，检索不到该文档。但详情、预览、下载全部 200，且该文档出现在文档列表里。

也就是说：受限文件夹内的文档，同库成员可以直接打开；被授例外的用户，只能看到一个检索片段而打不开文档。两条通道的读取口径都不如导出与引用严格。

### 缺陷 4：内容去重跨库命中时，目标库被静默忽略且回显

严重度：功能性与轻度信息暴露。上传时按内容摘要去重，命中**其他文档**时，请求里的 `target_library_id` 被丢弃，响应仍回显该目标库。

实测：

```
erin（d-hr 编辑，非 d-tech 成员）上传与 d-tech 文档同字节的文件，指定 target_library_id=p-beta
→ 201 {"document_id":"doc_iaykx3...","state":"ready","target_library_id":"p-beta","approval_request_id":null}
实际：该文档仍在 d-tech，未建审批请求，未进 p-beta
```

三个后果：

- 调用方以为上传到了目标库，实际留在原库，响应字段与事实不符。
- 未生成审批请求，绕过发布审批流程。
- 响应的 `document_id` 与 `version_id` 属于无权限者不可读的文档（erin 随后读该文档为 404），构成标识符暴露。

按 S3 设计，重复上传的「不建第二请求」是针对同一文档；跨文档的内容去重走入同一分支，语义在这里分叉了。

### 缺陷 5：示例配置缺 BM25 参数，导致 API 启动失败

`PIVOT_RETRIEVAL_BACKEND` 缺省为 `llama`，装配强制要求 `PIVOT_BM25_K1` 与 `PIVOT_BM25_B`。`ops/compose.env.example` 与 `ops/compose.staging.env.example` 都没有这两项：

```
RuntimeError: PIVOT_BM25_K1 and PIVOT_BM25_B are required when PIVOT_RETRIEVAL_BACKEND=llama
```

后果是按仓库文档执行 `docker compose --profile app up` 时 api 容器无法启动。属 ADR-020 与 LlamaIndex L4 切换默认后端后未回填 fixture 的遗留。

### 缺陷 6：示例公开下载地址被自家校验拒绝，导致 API 启动失败

`ops/compose.env.example` 中 `PIVOT_EXPORT_PUBLIC_BASE=http://127.0.0.1:8000/files`，而 `PublicDownloadSigner` 拒绝 loopback 与对象存储主机：

```
ValueError: download public_base must not be an object-store endpoint
```

仓库本地 `.env` 用的是 `https://files.pivot.test`，示例文件未同步。同样阻断 app profile 启动。

### 缺陷 7：MinIO 官方镜像不可用，对象存储来源缺失

| 来源 | 结果 |
| --- | --- |
| Docker Hub `minio/minio:RELEASE.2024-10-02T17-50-41Z` | 仓库不存在，`pull access denied` |
| Docker Hub 仓库 API `hub.docker.com/v2/repositories/minio/minio` | `object not found` |
| `quay.io/minio/minio` 匿名拉取 | 401 Unauthorized |
| `dl.min.io` 下载 | 410 Gone |

即 MinIO 已停止社区分发。本轮改用 memory 对象存储继续联调，因此真实对象字节链路未验证。可考虑的替代是社区维护分支 `pgsty/silo`（原 `pgsty/minio`，Pigsty 出品，AGPLv3，MinIO fork，环境变量兼容，持续发布）。选用它属于 fixture 供应链变更，需要 Owner 批准并登记变更记录，本轮未采用。

## 观测项（非缺陷，或需 Owner 确认口径）

1. **移动请求的 `reconcile_status` 恒为 `pending`**：批准后调和实际已生效（按库集合已正确），但状态字段停在 `pending` 且 `attempts=0`。这与 `progress/modules/M01.md` S4 记录的一致：worker 侧没有 move 请求行句柄，完成态回写缺失。同步模式下也如此，管理员按该字段判断会一直看到「未完成」。
2. **跨部门移动要求提议人同时是目标库成员**：移动目标校验复用上传校验（ADR-019 D2）。因此部门管理员把文档移到别的部门时，必须先被加入目标部门，否则 404。机制符合设计，但「A 部门管理员移交给 B 部门」这一常见场景默认不可用。已记在 `progress/modules/M01.md` 的残留里，本轮实测确认。
3. **决策类错误码与文档口径不一致（3 处）**：已决后复核读、已决后改目标、已删文档上的决策，实测均为 403 `RESOURCE_FORBIDDEN`；`progress/modules/M01.md` 分别写作 `illegal_state` 与 `not_found`。行为是保守拒绝，不影响安全，但文档与实现需对齐。
4. **60 天上限只对纯项目负责人生效**：`alice` 既是 `d-tech` 部门管理员又是 `p-alpha` 负责人，给她授 61 天与永久都成功；换 `bob`（只当 `p-beta` 负责人）后，61 天与永久都返回 422。这与 ADR-017 Q1「部门管理员不受限」一致，测试设计时须区分 grantor 身份，否则会误判为缺陷。
5. **首登强制改密是 403，不是 401**：未改密前访问受保护接口返回 403 `AUTH_PASSWORD_CHANGE_REQUIRED`，符合 ND-GAP-03 的预期行为，记录在此以免被误判。
6. **重复内容上传返回既有文档**：同一字节内容重复上传返回既有 `document_id` 与 `version_id`，不产生新版本。这是设计行为；缺陷 4 是它在跨文档命中时的分支问题。

## 收尾状态

| 对象 | 数量 |
| --- | --- |
| `documents` | 14 |
| `document_versions` | 14 |
| `chunks` | 16 |
| `libraries` | 6（`pub`、`unassigned`、`d-tech`、`d-hr`、`p-alpha`、`p-beta`） |
| `folders` | 2 |
| `memberships` | 11 |
| `approval_requests` | 7 |
| `move_requests` | 1 |
| `audit_events` | 191 |

Qdrant 集合：`pivot_local`（16 点，含陈旧 payload）、`pivot_local__llama__d-tech`（6）、`pivot_local__llama__d-tech__f-2026`（1）、`pivot_local__llama__d-hr`（2）、`pivot_local__llama__unassigned`（6）。基础集合点数多于按库集合之和，是陈旧 payload 未被清理的直接体现。

## 未验证范围

- Celery worker 与 broker：本轮 `PIVOT_INGEST=sync`，未起 worker，任务队列、重试与认领同步未验证。
- 真实对象存储字节链路：对象存储为 memory，见缺陷 7。
- QA 与 Agent 链路：`PIVOT_LLM=local`，只验证了检索与文档链路；QA 走 llama 按库集合，未实际提问。
- 真实供应商：`PIVOT_EMBEDDING=hash`，未接真实嵌入与重排服务。
- 容量与性能：未跑 100k chunk、5 路并发检索压测、P95 峰值。
- 备份恢复与灾备：未验证。
- 前端：未在浏览器中验证页面，只用 HTTP 接口。
- `GATE-P0-001~008`：全部仍 unverified，本轮不改变任何门槛状态。

## 本机配置（不入库）

| 路径/对象 | 说明 |
| --- | --- |
| `.env.real-deps` | 本轮联调环境变量，被 `.env.*` 规则忽略 |
| `.gitignore` | 追加 `*.db`、`*.db-journal`、`*.db-wal`、`*.db-shm`、`*.sqlite`、`*.sqlite3` |
| `/etc/systemd/system/docker.service.d/pivot-proxy.conf` | Docker daemon 代理 drop-in，系统级，不入仓库 |
| API 进程 | `uvicorn pivot.http.main:app --factory` 监听 `127.0.0.1:8010` |
| 测试数据 | 全为合成样本，无企业文档、无真实密钥 |

## 下一步

1. 修缺陷 1：先写变更申请与 Red 测试，再动代码。候选方案一是构建记录时按实时事实回填 `library_id`，方案二是调和时同步更新基础集合 payload。
2. 修缺陷 3：把文档读取路由接到 `AccessControl.authorize_document`，或把文件夹与例外通道并入 `_visible_document`。这涉及权限口径，需要 ADR 或变更申请确认。
3. 修缺陷 2：确认 BM25 腿的预期归属，补齐 `/search` 的索引装载，或明确降级为 dense-only 并修文档。
4. 修缺陷 4：跨文档内容去重时不得静默丢弃目标库，也不得向无权限者回显既有文档标识。
5. 修缺陷 5、6：只改两个 `.example` 文件，让「照文档能否起来」从失败变为通过。
6. 定缺陷 7：确认替代 S3 实现后改 compose 并登记变更记录。
7. 观测项 3 的文档口径需与实现对齐；观测项 1、2 属既有残留，随缺陷 1 与移动链路一并处置。

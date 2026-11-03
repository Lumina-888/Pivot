# 2026-11-03 本机真实依赖联调证据

## 范围与授权

- 输入基线 `main` `0587a73`（与 `origin/main` 一致），联调在本机工作区 `/home/lumina888/Projects/Pivot` 执行。
- Owner 要求在本机做真实依赖联调，验证系统可用性；不租用云主机，不做 staging 部署。
- 本轮只覆盖本机 loopback fixture。结论不等于 staging、生产或 GATE 验收，`GATE-P0-001~008` 仍全部 unverified。
- 未修改业务源码、公开契约、迁移、依赖锁与 `TBD-P0`。仓库内改动只有 `.gitignore` 追加本地 SQLite 忽略规则（未提交）。
- 私密配置写入 gitignored 的 `.env.real-deps`；登录口令不写入本文件。

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

Docker daemon 原无代理配置，直连 Docker Hub 超时（`dial tcp [2a03:2880:...]:443: i/o timeout`）。本机 Clash 监听 `127.0.0.1:7897`，`curl -x` 访问 `registry-1.docker.io` 返回 401，说明代理链路可用。按仓库既有脚本新增 systemd drop-in 后 daemon 生效：

```bash
pkexec /usr/bin/bash "$PWD/.pi/artifacts/local-linux-20261003/configure-docker-proxy.sh"
```

脚本只新增 `/etc/systemd/system/docker.service.d/pivot-proxy.conf`，内容为 `HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY` 三个环境变量，并执行 `systemctl daemon-reload` 与 `systemctl restart docker.service`；未修改 `/etc/docker/daemon.json`。

## 回归基线

联调前在 `0587a73` 上跑过的三组检查：

| 检查 | 结果 |
| --- | --- |
| `pytest -q tests/unit/auth tests/security/auth` | 271 passed（43.05 秒） |
| `pytest -q tests/integration/pipeline` | 380 passed，20 skipped（312.18 秒） |
| `npm --prefix web test` | 18 passed |

首次收集 `tests/integration/pipeline` 时两个模块 ImportError：`.venv` 缺 `llama-index-vector-stores-qdrant==0.3.3`。该包在 `api/pyproject.toml` 主依赖中，属于本机环境漂移。补装后全绿，未改动仓库依赖声明。

## 启动真实依赖

```bash
cd /home/lumina888/Projects/Pivot
docker compose --env-file ops/compose.env.example pull postgres qdrant redis
docker compose --env-file ops/compose.env.example up -d postgres qdrant redis
```

| 容器 | 端口 | 健康 |
| --- | --- | --- |
| `pivot-deps-postgres-1` | `127.0.0.1:5432` | accepting connections |
| `pivot-deps-qdrant-1` | `127.0.0.1:6333` | `all shards are ready` |
| `pivot-deps-redis-1` | `127.0.0.1:6379` | `PONG` |

`minio` 未启动，原因见问题 4。

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
| `GET /readyz` | `{"status":"not_ready","checks":{"postgres":true,"minio":false,"qdrant":true,"redis":true}}` |

`minio` 为 false 是本轮预期：对象存储临时走 memory，因为官方镜像不可用（问题 4）。

## 业务链路验证

账号：`local-admin`（总管理员，bootstrap 用户）、`alice`（`d-tech` 部门管理员）、`bob`（`d-tech` 编辑）、`carol`（无部门成员）。

| 步骤 | 调用 | 结果 |
| --- | --- | --- |
| 登录 | `POST /api/v1/auth/login` | 200，返回 access token 与 refresh Cookie |
| 建用户 | `POST /api/v1/admin/users` | 201，三个用户落 PG |
| 首次改密强制 | `POST /api/v1/auth/login` → `must_change_password: true` → `POST /api/v1/auth/change-password` | 204，改密后重新登录成功 |
| 建部门 | `POST /api/v1/admin/departments` | 201，`library_id=d-tech`、`kind=department` |
| 成员授权 | `POST /api/v1/admin/departments/d-tech/members` | 201，`dept_admin` 与 `editor` 两行落 PG |
| 上传（不选库） | `POST /api/v1/documents` | 200，`state=uploaded`，`target_library_id=null` |
| 解析与索引 | 同步 ingest | 版本转 `ready`，chunk 落 PG，向量进 Qdrant |
| 认领 | `POST /api/v1/admin/documents/{id}/claim` | 200，`library_id` 由 `unassigned` 改为 `d-tech` |
| 文档可见性 | `GET /api/v1/documents`、`GET /api/v1/documents/{id}` | 200，认领后部门成员可见 |
| 检索（管理员） | `GET /api/v1/search?q=...` | 命中，可返回 `title` 与 `snippet` |
| 检索（部门成员） | `GET /api/v1/search?q=...` | 0 命中，见问题 1 |

顺带观察到一条既有语义：同一文件字节重复上传会返回既有的 `document_id` 与 `version_id`。内容去重与幂等键两路都如此，未产生新版本。这是设计行为，不是缺陷。

## 发现的问题

### 问题 1：认领后库成员检索不到文档

严重度：功能性。部门成员在自己部门的库里搜不到已经认领的文档，管理员可以搜到。用户可见后果是「上传并入库了，但同事搜不到」。

#### 复现步骤

```bash
# 1) 管理员上传（不指定目标库），等待 ingest 完成
curl -X POST $API/api/v1/documents -H "$ADMIN" \
  -F "title=差旅制度2026" -F "file=@/tmp/pivot-travel.pdf;type=application/pdf"
# 2) 部门成员检索：0 命中（正确，文档仍在 unassigned）
# 3) 部门管理员认领到 d-tech
curl -X POST $API/api/v1/admin/documents/$DOC/claim -H "$ADMIN" \
  -H "Content-Type: application/json" -d '{"library_id":"d-tech"}'
# 4) 部门成员再次检索：0 命中（错误，预期 1 命中）
# 5) 管理员检索：2 命中（无库过滤，能搜到）
```

#### 证据

Qdrant 三个集合在同一时刻的 payload：

| 集合 | 点数 | `payload.library_id` |
| --- | --- | --- |
| `pivot_local`（基础集合） | 5 | `unassigned` |
| `pivot_local__llama__d-tech`（按库集合） | 5 | `d-tech` |
| `pivot_local__llama__unassigned` | 0 | — |

检索侧把命中的 chunk 解析成记录时，取到的是基础集合上的陈旧 payload：

```
chk_J9ibrkTg5F -> ('unassigned', 'doc_KCtGT3Kx')
chk_wZ7HidOApe -> ('unassigned', 'doc_KCtGT3Kx')
chk_nwKZNA8_Lz -> ('unassigned', 'doc_eDdYRofT')
```

再用同一 principal 做两次对照查询，可见过滤结果由这条陈旧字段决定：

| `library_ids` | 命中数 |
| --- | --- |
| `("unassigned",)` | 1 |
| `("d-tech",)` | 0 |

#### 根因

`GET /api/v1/search` 的检索链路与 QA 链路不是同一套：

| 链路 | retriever | 读取的 Qdrant 集合 |
| --- | --- | --- |
| `/api/v1/search` | `pivot.retrieval.vector.VectorStoreRetriever` | 基础集合 `pivot_local` |
| QA（`qa_retriever`） | `LlamaIndexRetriever` | 按库集合 `pivot_local__llama__<库>` |

由此形成三个环节叠加：

- 认领与移动的调和只更新按库的 llama 集合，基础集合 `pivot_local` 上的 payload 保持旧库值。
- `/search` 的 dense 腿直接读基础集合，构建 `ChunkRecord` 时以 payload 里的 `library_id` 为准，未按实时文档事实回填。
- `passes_filters()` 用该字段与调用者可见库集合比对，把合法命中判为越权并丢弃。

三个环节缺一不可：单看任一处都不会表现为「成员搜不到」。

#### 影响范围

- 只影响 `/api/v1/search`。QA 链路走 llama 按库集合，payload 正确，推测不受影响，本轮未验证。
- 认领（P1-2 S5、P1-1）与跨库移动审批（P1-3 S4）都走同一调和入口，移动后的搜索应同样受影响，本轮未单独验证。
- 文件夹移动（P1-4）复用同一 reconcile 形状，存在同类风险。
- 不构成越权泄漏：过滤方向是「拒绝过多」，不是「放行过多」。授权钩子按实时事实判定的设计仍然成立。

### 问题 2：示例配置缺 BM25 参数，导致 API 启动失败

`PIVOT_RETRIEVAL_BACKEND` 缺省为 `llama`，装配时强制要求 `PIVOT_BM25_K1` 与 `PIVOT_BM25_B`。`ops/compose.env.example` 与 `ops/compose.staging.env.example` 都没有这两项，实测启动直接失败：

```
RuntimeError: PIVOT_BM25_K1 and PIVOT_BM25_B are required when PIVOT_RETRIEVAL_BACKEND=llama
```

后果是按仓库文档执行 `docker compose --profile app up` 时 api 容器无法启动。属 ADR-020 与 LlamaIndex L4 切换默认后端后未回填 fixture 的遗留。

### 问题 3：示例公开下载地址被自家校验拒绝，导致 API 启动失败

`ops/compose.env.example` 中 `PIVOT_EXPORT_PUBLIC_BASE=http://127.0.0.1:8000/files`。`PublicDownloadSigner` 明确拒绝 loopback 与对象存储主机：

```
ValueError: download public_base must not be an object-store endpoint
```

仓库本地 `.env` 用的是 `https://files.pivot.test`，示例文件未同步。同样阻断 app profile 启动。

### 问题 4：MinIO 官方镜像不可用，对象存储来源缺失
| 来源 | 结果 |
| --- | --- |
| Docker Hub `minio/minio:RELEASE.2024-10-02T17-50-41Z` | 仓库不存在，`pull access denied` |
| Docker Hub 仓库 API `hub.docker.com/v2/repositories/minio/minio` | `object not found` |
| `quay.io/minio/minio` 匿名拉取 | 401 Unauthorized |
| `dl.min.io` 下载 | 410 Gone |

即 MinIO 已停止社区分发。本轮改用 memory 对象存储继续联调，因此上传、预览、下载的真实字节链路未验证。

可考虑的替代实现是社区维护分支 `pgsty/silo`（原 `pgsty/minio`，Pigsty 出品，AGPLv3，MinIO fork，环境变量兼容，持续发布）。选用它属于 fixture 供应链变更，需要 Owner 批准并登记变更记录，本轮未采用。

### 问题 5：`/search` 的 BM25 腿一直是空索引

严重度：功能性（检索质量）。`/api/v1/search` 装配了两个 retriever，实测 BM25 一路的索引从未装载：

```
bm25 索引文档数: 0
dense retriever: pivot.retrieval.vector.VectorStoreRetriever
qa_retriever:   pivot.retrieval.llama_index_retriever.LlamaIndexRetriever
```

`Bm25Retriever.add()` 只在 llama 检索器内部被调用，`/search` 用的那个实例在装配后没有被填充，`corpus` 传的是空元组。后果是 `/search` 实际只有 dense 单腿，RRF 融合退化为单路排序。

这与已修复的 FR-RAG-009 是同一类形态，只是方向相反：那次是 dense 静默失效、退化为 BM25 单腿，这次是 BM25 恒空、退化为 dense 单腿。文档搜索名义上是 dense + BM25 双路，实测不是。

## 未验证范围

- Celery worker 与 broker 路径：本轮 `PIVOT_INGEST=sync`，未起 worker 容器，任务队列、重试与认领同步未验证。
- 真实对象存储字节链路：对象存储为 memory，见问题 4。
- QA 链路：问题 1 的影响范围里已说明 QA 走 llama 按库集合，本轮未实际提问验证。
- 审批流：发布审批、自批快线、移动审批、复核读、待办队列均未执行。
- 授权细化：文档级例外、临时授权到期、文件夹隔离与可见性并集未执行。
- 并发与容量：多用户并发上传、5 并发检索、100k chunk 未执行。
- 重启保持：进程重启后的事实与向量一致性未单独验证（本轮重启仅用于排除缓存因素）。
- 真实供应商：`PIVOT_LLM=local`、`PIVOT_EMBEDDING=hash`，未接真实模型与嵌入服务。
- `GATE-P0-001~008`：全部仍 unverified，本轮不改变任何门槛状态。

## 本机配置（不入库）

| 路径/对象 | 说明 |
| --- | --- |
| `.env.real-deps` | 本轮联调环境变量，被 `.env.*` 规则忽略 |
| `.gitignore` | 追加 `*.db`、`*.db-journal`、`*.db-wal`、`*.db-shm`、`*.sqlite`、`*.sqlite3`（未提交） |
| `/etc/systemd/system/docker.service.d/pivot-proxy.conf` | Docker daemon 代理 drop-in，系统级，不入仓库 |
| API 进程 | `uvicorn pivot.http.main:app --factory` 监听 `127.0.0.1:8010`，本轮回联调结束后可停止 |
| 测试数据 | PG 内 2 个文档、2 个版本、5 个 chunk；Qdrant 3 个集合；均为合成样本 |

## 下一步

1. 修问题 1：先写变更申请与 Red 测试，再改检索侧或调和侧。候选方案一是构建记录时按实时事实回填 `library_id`，方案二是调和时同步更新基础集合 payload。
2. 修问题 5：确认 BM25 腿的预期归属，补齐 `/search` 的索引装载或明确降级为 dense-only 并修文档。
3. 修问题 2、3：只改两个 `.example` 文件，让「照文档能否起来」从失败变为通过。
4. 定问题 4：确认替代 S3 实现后改 compose 并登记变更记录。
5. 继续扩大联调覆盖：审批与移动全链、例外与文件夹隔离、重启保持、Celery 路径。

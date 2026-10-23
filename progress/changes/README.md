# 变更申请索引

本目录存放各模块的变更申请与设计提案，文件名的格式是 `YYYYMMDD-模块-主题.md`。
本索引按月份分组，标题取自各文件的一级标题。新增变更申请时，同步在本索引的对应月份下登记一行。

## 2026 年 9 月

| 文件 | 标题 |
|---|---|
| [20260906-M00-contract-test-path.md](20260906-M00-contract-test-path.md) | 变更申请：Wave 0 期间 `tests/contract/**` 根级文件由 M00 承载 |
| [20260906-M01-auth-dependencies.md](20260906-M01-auth-dependencies.md) | 变更申请：M01 认证依赖 argon2-cffi（及可选 PyJWT） |
| [20260906-M03-ownership-clarification.md](20260906-M03-ownership-clarification.md) | 变更申请：M03 依赖配置与 shared 路径所有权澄清 |
| [20260906-M05-langgraph.md](20260906-M05-langgraph.md) | 历史变更申请：M05 可选 LangGraph 依赖（superseded） |
| [20260906-M06-observability-package-init.md](20260906-M06-observability-package-init.md) | 变更申请：M06 观测审计包初始化文件 |
| [20260906-M07-worker-dependencies.md](20260906-M07-worker-dependencies.md) | 变更申请：M07 解析/队列可选依赖 |
| [20260906-M08-web-scaffold-ownership.md](20260906-M08-web-scaffold-ownership.md) | 变更申请：Wave 0 Web 工程骨架与共享工具所有权澄清 |
| [20260907-M02-documents-lifecycle-http.md](20260907-M02-documents-lifecycle-http.md) | 变更申请：扩展 /api/v1/documents 详情、版本、重试与删除 |
| [20260907-M11-api-v1-auth-mount.md](20260907-M11-api-v1-auth-mount.md) | 变更申请：M11 挂载注入的 /api/v1 认证路由 |
| [20260907-M11-api-v1-documents-mount.md](20260907-M11-api-v1-documents-mount.md) | 变更申请：M11 挂载注入的 /api/v1 文档上传与列表路由 |
| [20260907-M11-api-v1-runs-sse-mount.md](20260907-M11-api-v1-runs-sse-mount.md) | 变更申请：M11 挂载注入的 /api/v1/runs 与 SSE |
| [20260907-M11-api-v1-search-mount.md](20260907-M11-api-v1-search-mount.md) | 变更申请：M11 挂载注入的 /api/v1/search |
| [20260907-M11-fastapi-health-assembly.md](20260907-M11-fastapi-health-assembly.md) | 变更申请：M11 薄 HTTP 装配仅健康检查 |
| [20260908-M00-mainline-development.md](20260908-M00-mainline-development.md) | 变更申请：废止默认并行 worktree，改为主线开发 |
| [20260908-M01-auth-admin-users-http.md](20260908-M01-auth-admin-users-http.md) | 变更申请：扩展 /api/v1/auth/change-password 与 /admin/users |
| [20260908-M02-documents-preview-download-http.md](20260908-M02-documents-preview-download-http.md) | 变更申请：扩展 /api/v1/documents 预览与下载 |
| [20260908-M11-api-v1-conversations-mount.md](20260908-M11-api-v1-conversations-mount.md) | 变更申请：M11 挂载注入的 /api/v1/conversations |
| [20260908-M11-api-v1-export-audit-mount.md](20260908-M11-api-v1-export-audit-mount.md) | 变更申请：M11 挂载注入的 /api/v1/exports 与 /admin/audit-events |
| [20260909-M03-minio-object-store.md](20260909-M03-minio-object-store.md) | 变更申请：M03 MinIO ObjectStore 客户端 |
| [20260909-M03-postgres-user-directory.md](20260909-M03-postgres-user-directory.md) | 变更申请：M03 PostgreSQL 用户事实源客户端 |
| [20260909-M03-qdrant-vector-store.md](20260909-M03-qdrant-vector-store.md) | 变更申请：M03 Qdrant VectorStore 客户端 |
| [20260909-M03-redis-cache-queue.md](20260909-M03-redis-cache-queue.md) | 变更申请：M03 Redis CacheStore / QueueStore 客户端 |
| [20260909-M04-bm25-rerank.md](20260909-M04-bm25-rerank.md) | 变更申请：M04 stdlib BM25 与可注入 rerank |
| [20260909-M04-http-embedding-bge-rerank.md](20260909-M04-http-embedding-bge-rerank.md) | 变更申请：M04 HTTP Embedding 与 bge-reranker 适配器 |
| [20260909-M04-qdrant-retrieval.md](20260909-M04-qdrant-retrieval.md) | 变更申请：M04 检索 dense 路消费 Qdrant VectorStore |
| [20260909-M08-next-api-proxy.md](20260909-M08-next-api-proxy.md) | 变更申请：Next 反代 `/api/v1` |
| [20260909-M11-capacity-backup-fixture.md](20260909-M11-capacity-backup-fixture.md) | 变更申请：M11 5 并发夹具与进程内备份恢复 |
| [20260909-M11-chunk-capacity.md](20260909-M11-chunk-capacity.md) | 变更申请：M11 100k Chunk opt-in 容量夹具 |
| [20260909-M11-compose-api.md](20260909-M11-compose-api.md) | 变更申请：M11 Dockerfile 与 Compose api 服务 |
| [20260909-M11-compose-web.md](20260909-M11-compose-web.md) | 变更申请：M11 Dockerfile.web 与 Compose web 服务 |
| [20260909-M11-composition-root.md](20260909-M11-composition-root.md) | 变更申请：M11 composition root（可启动 FastAPI） |
| [20260909-M11-golden-set-synthetic.md](20260909-M11-golden-set-synthetic.md) | 变更申请：M11 Golden Set v0.1-synthetic 检索回归夹具 |
| [20260909-M11-golden-set-v02.md](20260909-M11-golden-set-v02.md) | 变更申请：M11 Golden Set v0.2-synthetic（100~150 条） |
| [20260909-M11-minio-export-objects.md](20260909-M11-minio-export-objects.md) | 变更申请：M11 导出对象接到 MinIO（仍用 PublicDownloadSigner） |
| [20260909-M11-playwright-login.md](20260909-M11-playwright-login.md) | 变更申请：opt-in Playwright 浏览器登录 |
| [20260910-M00-dev-staging-scope.md](20260910-M00-dev-staging-scope.md) | 变更申请：开发调试环境范围（非 SPEC 生产上线） |
| [20260910-M00-dev-staging-vendors.md](20260910-M00-dev-staging-vendors.md) | 变更申请：dev-staging 供应商注入清单（不入库、不冻 TBD-P0） |
| [20260910-M01-compose-login-rate.md](20260910-M01-compose-login-rate.md) | 变更申请：Compose api 注入登录限流阈值/窗口（接到 Redis） |
| [20260910-M01-redis-login-rate-limit.md](20260910-M01-redis-login-rate-limit.md) | 变更申请：登录失败限流计数接到 Redis CacheStore |
| [20260910-M03-postgres-document-facts.md](20260910-M03-postgres-document-facts.md) | 变更申请：PostgreSQL 文档事实源（Document/Version/Chunk/Task） |
| [20260910-M07-celery-ingest.md](20260910-M07-celery-ingest.md) | 变更申请：M07 Celery ingest 可见 PostgreSQL version/task |
| [20260910-M07-ingest-qdrant.md](20260910-M07-ingest-qdrant.md) | 变更申请：M07 ingest 索引代次写入 VectorStore（Qdrant 端口） |
| [20260910-M07-worker-minio-ingest.md](20260910-M07-worker-minio-ingest.md) | 变更申请：worker 装配共享 MinIO/PG ingest runner |
| [20260910-M07-worker-qdrant-index.md](20260910-M07-worker-qdrant-index.md) | 变更申请：worker 装配 Qdrant IndexPublisher |
| [20260910-M11-compose-api-celery-ingest.md](20260910-M11-compose-api-celery-ingest.md) | 变更申请：Compose api 注入 `PIVOT_INGEST=celery` |
| [20260910-M11-compose-api-shared-storage.md](20260910-M11-compose-api-shared-storage.md) | 变更申请：Compose api 注入共享 PG/MinIO |
| [20260910-M11-compose-api-worker-qdrant-redis.md](20260910-M11-compose-api-worker-qdrant-redis.md) | 变更申请：Compose api/worker 注入 Qdrant/Redis |
| [20260910-M11-compose-celery-worker.md](20260910-M11-compose-celery-worker.md) | 变更申请：Compose worker 以 Celery 消费 Redis broker（parse 队列） |
| [20260910-M11-compose-worker.md](20260910-M11-compose-worker.md) | 变更申请：M11 Dockerfile.worker 与 Compose worker 服务 |
| [20260910-M11-http-upload-ingest.md](20260910-M11-http-upload-ingest.md) | 变更申请：HTTP 上传后进程内自动 ingest（非 Celery） |
| [20260910-M11-wave3-closeout.md](20260910-M11-wave3-closeout.md) | 变更申请：Wave 3 夹具收口评审（ND-W3-13） |
| [20260914-M01-admin-patch-role-reset.md](20260914-M01-admin-patch-role-reset.md) | 变更申请：PATCH /admin/users 角色变更与重置密码 HTTP |
| [20260914-M01-postgres-refresh-conversations.md](20260914-M01-postgres-refresh-conversations.md) | 变更申请：会话 / refresh 跨进程存储 |
| [20260914-M05-http-draft-writer.md](20260914-M05-http-draft-writer.md) | 变更申请：Deepseek-Flash Draft Writer 适配器（CI Fake HTTP） |
| [20260914-M05-postgres-run-eventlog.md](20260914-M05-postgres-run-eventlog.md) | 变更申请：Run / EventLog 跨进程存储 |
| [20260914-M05-sse-long-connection.md](20260914-M05-sse-long-connection.md) | 变更申请：SSE 长连接推送与前端去缓冲 |
| [20260914-M06-postgres-export-tasks.md](20260914-M06-postgres-export-tasks.md) | 变更申请：导出任务 PostgreSQL 持久化 |
| [20260914-M07-ingest-http-embedding.md](20260914-M07-ingest-http-embedding.md) | 变更申请：ingest 与检索共用注入 HTTP Embedding |
| [20260914-M07-mineru-cloud-parser.md](20260914-M07-mineru-cloud-parser.md) | 变更申请：MinerU 云 API 解析器（CI Fake HTTP） |
| [20260914-M07-native-parsers.md](20260914-M07-native-parsers.md) | 变更申请：真实解析库 extra（PyMuPDF / python-docx / python-pptx / openpyxl） |
| [20260914-M11-compose-staging.md](20260914-M11-compose-staging.md) | 变更申请：dev-staging Compose overlay（4C8G 主机档，不 SSH 冒充上机） |
| [20260914-M11-golden-set-enterprise-fill.md](20260914-M11-golden-set-enterprise-fill.md) | 变更申请：填写企业 Golden Set v0.3（脱敏项目摘录，非 GATE） |
| [20260914-M11-golden-set-enterprise-schema.md](20260914-M11-golden-set-enterprise-schema.md) | 变更申请：企业 Golden Set 标注规范与空 schema（不合成样本） |
| [20260914-M11-playwright-ten-pages.md](20260914-M11-playwright-ten-pages.md) | 变更申请：opt-in Playwright 十页 |

## 2026 年 10 月

| 文件 | 标题 |
|---|---|
| [20261002-M00-langgraph-react-baseline.md](20261002-M00-langgraph-react-baseline.md) | ADR-009：LangGraph 受控 ReAct Agent 规格基线 |
| [20261002-M00-spec-to-tickets.md](20261002-M00-spec-to-tickets.md) | SPEC-1.1 按当前进度拆分剩余 Tickets |
| [20261002-M03-agent-dependencies-lock.md](20261002-M03-agent-dependencies-lock.md) | ND-AGENT-02-C：Python 3.12 框架依赖验证与锁定申请 |
| [20261002-M05-agent-budget-contract.md](20261002-M05-agent-budget-contract.md) | ND-AGENT-02-B：DR-010 预算与累计用量 Contract 提案 |
| [20261002-M05-agent-internal-contract.md](20261002-M05-agent-internal-contract.md) | ND-AGENT-02-A：模型、工具与状态内部 Contract 提案 |
| [20261002-M05-answer-safety.md](20261002-M05-answer-safety.md) | ND-AGENT-01：答案安全门禁实施 Contract |
| [20261003-M00-agent-resume-contract.md](20261003-M00-agent-resume-contract.md) | ND-AGENT-03-A 澄清恢复公开 Contract 提案 |
| [20261003-M03-agent-persistence-contract.md](20261003-M03-agent-persistence-contract.md) | ND-AGENT-04-A checkpoint、租约、事实与 outbox Contract 提案 |
| [20261003-M11-agent-supply-chain-evidence.md](20261003-M11-agent-supply-chain-evidence.md) | ND-AGENT-02-C 离线供应链材料补齐 |
| [20261003-M11-local-linux-environment.md](20261003-M11-local-linux-environment.md) | 2026-10-03 本机 Linux 开发环境与清华默认源 |
| [20261003-M11-ubuntu-tuna-validation.md](20261003-M11-ubuntu-tuna-validation.md) | ND-AGENT-02-C 清华源与 Ubuntu 源码构建诊断 |
| [20261004-M11-agent-public-supply-chain-check.md](20261004-M11-agent-public-supply-chain-check.md) | ND-AGENT-02-C：公开漏洞查询与上游许可证材料 |
| [20261004-M11-candidate-compression-errors.md](20261004-M11-candidate-compression-errors.md) | ND-AGENT-02-C：压缩候选 wheel 错误脱敏回归 |
| [20261004-M11-candidate-hidden-artifacts.md](20261004-M11-candidate-hidden-artifacts.md) | ND-AGENT-02-C 隐藏目录证据上传修正 |
| [20261004-M11-candidate-integrity-tool.md](20261004-M11-candidate-integrity-tool.md) | ND-AGENT-02-C：离线候选材料一致性工具 |
| [20261004-M11-candidate-ubuntu-ci-preparation.md](20261004-M11-candidate-ubuntu-ci-preparation.md) | ND-AGENT-02-C：Ubuntu 手动候选 CI 验证入口准备 |
| [20261004-M11-private-env-regression.md](20261004-M11-private-env-regression.md) | M11 本机私有环境配置回归修正 |
| [20261004-M11-ubuntu-candidate-rebuild.md](20261004-M11-ubuntu-candidate-rebuild.md) | ND-AGENT-02-C Ubuntu 候选锁与双离线重建 |
| [20261011-M04-llama-index-retrieval.md](20261011-M04-llama-index-retrieval.md) | ADR-010：Phase 1 LlamaIndex 检索适配（本机开发） |
| [20261012-M11-admin-metrics-tasks.md](20261012-M11-admin-metrics-tasks.md) | ND-GAP-01：后台指标与任务 HTTP 路由 |
| [20261021-M05-agent-model-selection.md](20261021-M05-agent-model-selection.md) | ADR-011：Agent 模型选型（主、测试与备用） |
| [20261022-M11-admin-metrics-tasks-wiring.md](20261022-M11-admin-metrics-tasks-wiring.md) | ND-GAP-01：问答计数与任务列表改读持久化存储 |
| [20261022-M06-audit-persistence-tiered-failure.md](20261022-M06-audit-persistence-tiered-failure.md) | ND-GAP-02：审计统一落库与分级失败策略 |
| [20261022-M01-password-change-persistence-enforcement.md](20261022-M01-password-change-persistence-enforcement.md) | ND-GAP-03：首次改密落库与服务端强制 |
| [20261022-M06-export-signed-download-consumer.md](20261022-M06-export-signed-download-consumer.md) | ND-GAP-04：签名导出下载消费者端点 |
| [20261022-M06-export-admin-download.md](20261022-M06-export-admin-download.md) | ADR-012：导出下载的管理员访问 |
| [20261023-M05-qa-engine-switch.md](20261023-M05-qa-engine-switch.md) | ADR-013：问答引擎开关与 Agent 生产装配（W1） |
| [20261023-M05-agent-execution-binding.md](20261023-M05-agent-execution-binding.md) | W2：Agent 结局对接 Run 状态机与 SSE |

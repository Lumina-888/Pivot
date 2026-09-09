# 备份恢复 Runbook（未演练）

> **状态**：程序草稿。`NFR-DR-001~004` / `GATE-P0-006` **未验证**。  
> 初始口径：RPO ≤ 24h、RTO ≤ 4h；最终值须 P0 新 ECS 演练后冻结，本文件不填替代值。

## 备份对象

1. PostgreSQL（用户、文档版本、Run、审计、导出任务元数据）；
2. MinIO（隔离上传对象与导出物）；
3. Qdrant snapshot 或可重建的索引配置 + 代次；
4. Compose/迁移版本与配置（不含 Secret 明文）；
5. 审计事件（追加写，恢复后必须仍在；恢复动作记 `ops.backup_restore`）。

Redis 只保存可重建队列/缓存/限流，**不是**业务事实源，丢失不得造成事实不可恢复。

进程内夹具：`ops/fact_backup.py` 可对 memory 用户目录/对象/向量点/审计做 roundtrip。**不是**加密 OSS，**不是**新 ECS 演练。

## 恢复步骤（目标环境，尚未执行）

1. 在新 ECS 上检出固定发布版本（禁止 `latest`）；
2. 恢复 PostgreSQL，跑迁移到该版本；
3. 恢复对象存储与向量快照（或按 ready/current 版本重建索引）；
4. 注入密钥，启动依赖并等待 health/ready（应用已有 `/healthz` `/readyz` 装配，尚未作为 Compose api 服务启动）；
5. 校验：用户可登录、文档列表、抽样 Chunk/向量/Citation、审计条数、抽样问答。

## 本波次限制

- 本地可有依赖 Compose fixture（postgres/minio/qdrant/redis）；应用健康端点仅 TestClient，未在新 ECS 演练；
- 无加密 OSS 备份作业；
- 无新 ECS 演练记录。证据目录不得把本 Runbook 当作已通过门禁。

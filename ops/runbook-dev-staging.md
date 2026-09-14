# dev-staging 启动 Runbook（未在 ECS 上机）

> **状态**：程序草稿。`NFR-CAP-006` / `GATE-P0-007` / `GATE-P0-008` **unverified**。  
> 阿里云 4C8G 只是 `dev-staging` 主机档，**不是**已冻生产规格，也不是 P0 容量/发布门禁通过。  
> 本文件**不**代替 Owner 的 SSH、安全组、数据盘和域名决策。

## 0. Owner 前置（缺一不可上机）

编码会话**不得**冒充已部署。上机前 Owner 必须给出：

1. **SSH**：主机地址、用户（需 sudo）、私钥或堡垒路径；密钥不入库；
2. **安全组**：入站默认只开 **22**。若走公网 HTTP，再开 **80**（有证书/域名后再开 **443**）。**禁止**放行 5432 / 6379 / 9000 / 6333 / 8000 / 3000 / 8001；
3. **磁盘**：系统盘之外的数据盘容量与挂载点（建议 `/var/lib/pivot`）。本 overlay 仍用 Compose named volumes；Owner 可在上机时改 bind，不在仓库写死云盘 ID；
4. **域名**：不要则用 SSH 隧道访问 `127.0.0.1:80`，或 Owner 明确要求后把 `PIVOT_STAGING_HTTP_BIND=0.0.0.0`。要域名则 Owner 提供证书后再挂 443（本切片 nginx 只听 80）；
5. **密钥**：硅基 Embedding/Rerank、DeepSeek、小米 fallback、MinerU token 只进服务器 gitignored `.env`，禁止提交。

未齐上述项时，只保留本仓库 overlay，**不要** `ssh` / 改安全组 / 格式化数据盘。

## 1. 本机/服务器命令（有 Docker 后）

```bash
cp ops/compose.staging.env.example .env
# 编辑 .env：替换口令与 token；live endpoint 由 Owner 注入
docker compose --env-file .env --profile app \
  -f docker-compose.yml -f docker-compose.staging.yml up -d
```

可选 systemd（把 `WorkingDirectory` 换成实际检出路径）：

```bash
sudo cp ops/pivot-staging.service /etc/systemd/system/pivot-staging.service
sudo systemctl daemon-reload
sudo systemctl enable --now pivot-staging.service
```

默认 `PIVOT_STAGING_HTTP_BIND=127.0.0.1`：本机或 SSH 隧道

```bash
ssh -L 8080:127.0.0.1:80 <user>@<host>
```

浏览器打开 `http://127.0.0.1:8080/login`。

## 2. 资源与模型约束

- overlay limits 总和约 6GiB，给 8GiB 主机留 OS 余量；数字是 fixture，**不是** `TBD-P0` 冻结值，**不是** `GATE-P0-007` 峰值证据；
- worker concurrency example 为 1，避免解析尖峰拖垮整机；
- **不自建** MinerU / LLM / Embedding / Rerank；全部走外部 API（Compose 已注入 `PIVOT_*`）；
- 文档仅低敏规章制度；禁止企业合同/人事薪酬进入 `dev-staging`。

## 3. 健康与回滚

冒烟：`/login` → 登录 → 上传低敏文档 → 检索 → 问答 → 导出。  
失败则 `docker compose --profile app -f docker-compose.yml -f docker-compose.staging.yml down` 后按 `ops/runbook-rollback.md`。本切片**未**做固定版本发布与回滚演练。

## 4. 明确不是

- 不是 SPEC「上线」；
- 不是加密 OSS 备份（`GATE-P0-006` 仍 unverified）；
- 不是 5 并发 / 100k / P95 实测（`GATE-P0-007` 仍 unverified）；
- 不是固定版本发布门禁（`GATE-P0-008` 仍 unverified）。

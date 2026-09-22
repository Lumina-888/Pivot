# 问枢 Pivot 后续开发规格（Wave 3 收口 → P0 闸门）

> **文档 ID**：`NEXT-DEV-1.14`  
> **日期**：2026-09-14  
> **基线**：`main` / tag 目标 `wave-3-integrated`（夹具收口，**不等于** P0 通过）。  
> **性质**：开发计划与工单拆分。  
> **本文件不是需求源。** 需求、状态机、错误码、API/SSE/Worker、GATE、`TBD-P0` 仍以 [`SPEC.md`](../SPEC.md) 为准；模块边界以 [`MODULE_SPEC.md`](../MODULE_SPEC.md) 为准；进度以 [`PROGRESS.md`](../PROGRESS.md) 为准。工单目录见 [`tickets.md`](tickets.md)。

与 SPEC 冲突时以 SPEC 为准。不得把本文件解释为已冻结 `TBD-P0`，不得把 Fake/夹具标成 `GATE-P0-*` verified。

Owner 已确认近期目标是 **`dev-staging`（开发者调试环境）**，不是 SPEC 生产上线。范围见 [`changes/20260910-M00-dev-staging-scope.md`](changes/20260910-M00-dev-staging-scope.md)。

---

## 0. 当前判断

产品处于 **Wave 3 夹具已收口**：领域服务 + HTTP + composition root + Compose fixture（api/web/worker，共享 PG/MinIO/Qdrant/Redis 注入；api 注入 celery ingest 与登录限流阈值/窗口；worker 可接 Qdrant；导出任务可走 SQLAlchemy；PATCH 角色/重置密码 HTTP；ingest/检索可共用注入 HTTP Embedding；可注入 HTTP Draft Writer 与 MinerU 云解析器；`PIVOT_PARSER=native` 可装配真实解析库 extra；dev-staging Compose overlay 已入库；hashed refresh、Conversation 与 Run/EventLog 可跨装配；SSE 长连接推送；opt-in Playwright 十页）已在 `main`。分组 Python 以本切片回归为准。

这不等于可上线：

| 层级 | 状态 |
|---|---|
| Fake/夹具实现 | 大量 `implemented` |
| Compose 本机 fixture | 文件在；CI 不 build/up |
| 真实 PG/MinIO/Qdrant/Redis/Celery 端到端 | 未验证 |
| `wave-3-integrated` | 夹具收口（≠ P0 通过） |
| `GATE-P0-001~008` | 全部 **unverified** |
| P1 进入 | 被 P0 八项阻断 |

SPEC §12.2：`GATE-P0-005` 不过禁止上线；`GATE-P0-006` 不过不得正式试用；`GATE-P0-003` 不过禁止生产上传。

---

## 1. 目标与非目标

### 1.1 目标

1. **Wave 3 工程收口**：Compose 上「上传 → 解析队列 → 共享对象/事实 → 索引 → 检索」可本机 opt-in 跑通（仍不是 GATE verified）。
2. **P0 闸门可验收**：真实（或受控 live）证据能对上 SPEC 八项门槛；该冻的 `TBD-P0` 经 ADR/实测写入 SPEC。
3. **P1 进入条件**：八项关闭 + 数据准入生效 + 契约已冻 + TDD/Fixture 已建（SPEC §12.3）。

### 1.2 非目标（本规格不排进 Wave 3）

- P2：OCR/复杂表格、对比、HITL、Text2SQL、页内高亮、SSO。
- P3：多机/K8s、密级 ACL、成本优化常态化。
- 私自给 `TBD-P0` 填生产默认值。
- 把合成 Golden Set、eager Celery、Fake MinIO/Embedding、opt-in 100k、Dockerfile fixture 标成 GATE verified。
- 会话内再合成「企业 Golden Set」。

---

## 2. 原则（沿用，不新发明）

1. 工作区仅 `E:/AI Project/Pivot` 的 `main`；不新建 worktree。
2. 先 `progress/changes/`，再业务代码；Red → Contract → Green。
3. 测试名 `test_<requirement_id>_<behavior>()`。
4. 外部 LLM/Embedding/Rerank/基础设施：CI 用 Fake/Stub；live 冒烟 opt-in，不提交密钥与企业文档。
5. 跨进程对象字节必须走共享 ObjectStore；内存对象不能当跨进程事实。
6. 影响状态机、权限、引用/删除、模型或检索配置必须 ADR（SPEC §0.6、附录 E）。
7. 一个切片可跨模块，但必须写明 Accountable；提交 `type(Mxx): 中文说明 [需求或测试 ID]`。

---

## 3. 阶段划分

```text
Phase A  Wave 3 工程收口（可编码，默认不标 GATE verified）
    A1 跨进程 ingest 闭环
    A2 持久化与管理缺口
    A3 体验/解析加固
        ↓  打 wave-3-integrated 的前提：A1 完成 + 回归绿 + 仍全部 GATE unverified 写进证据
Phase B  P0 闸门（人审 + 受控环境 + 实测冻 TBD）
    B1 合规与评测
    B2 一致性和安全
    B3 容量、灾备、发布
        ↓  八项 verified 后才进入 P1
Phase C  P1（10 页真实系统 + 矩阵）
```

### 3.1 `dev-staging` 轨道（Owner 当前目标）

```text
A1 跨进程 ingest（Qdrant + Celery）     ← 现在就编码，不需要云主机
    → STG live Embedding/Rerank（注入 HTTP，已有适配器）
    → STG Deepseek-Flash Writer（新适配器）
    → STG MinerU 解析器（SPEC V2 提前到 staging，CI 仍 Fake）
    → 阿里云 4C8G 部署 Compose           ← 这时才需要你租机器
```

约束：

- 用户仅 Owner/开发者；文档仅规章制度等低敏测试材料；**禁止**企业合同。
- 外发审批（`DR-001`）延期到企业化；**不**因此把 `GATE-P0-001/005` 标 verified。
- 密钥只进服务器 env；CI 仍 Fake；4C8G 不是 GATE 已验证规格。
- MinerU / LLM / Embedding / Rerank 全部走**外部 API**，不要装在 4C8G 上。

Phase A 可以与规章制度样本准备并行。**B 未完成前禁止把系统当 SPEC 生产上线 / 正式企业试用。**

---

## 4. 现状 → 缺口映射

| SPEC 范围 | 已有 | 缺口 | 阶段 |
|---|---|---|---|
| 文档事实 PG、对象 MinIO | HTTP/worker 可装配；Compose 已注入变量 | Compose 缺省仍 sync ingest；worker 未必选 Qdrant；无 live 一致性环境 | A1, B2 |
| Celery parse 队列 | extra + eager + Compose worker 只听 parse；Compose api 注入 celery ingest | 非 eager、非真实 Redis broker；CI 不 up | A1, B2 |
| 检索 dense+BM25 | Qdrant 端口 + stdlib BM25 + Fake/HTTP 适配；ingest/检索可共用注入 HTTP Embedding | 无 live embedding；Golden Set 合成 | A1, B1 |
| 解析 | 启发式 PDF + stdlib OOXML；可注入 native extra 与 MinerU 云 | 缺省仍启发式；OCR 属 P2；无 live MinerU | A3 |
| 导出 | HTTP + MinIO 字节 + signer；任务可走 SQLAlchemy（CI sqlite） | 无对象字节下载路由（契约如此，不单开破坏契约的票） | A2 |
| 认证 | 登录/改密/用户 HTTP；Redis 限流可注入；PATCH 角色/重置；hashed refresh 可走 SQLAlchemy（CI sqlite） | 阈值 TBD-P0；初始密码传递机制 TBD-P0 | A2, B2 |
| QA/SSE | 主图 + Run/SSE HTTP 长连接；Conversation 与 Run/EventLog 可走 SQLAlchemy（CI sqlite） | uvicorn 长连接为 opt-in skip；Claim/Citation 仍不入库；LangGraph extra 暂缓；Verifier 阈值未冻 | A3, B1 |
| Web | 10 页 Fake fetch；opt-in Playwright 十页；SSE 去缓冲 Route Handler | 企业标注与 live 冒烟仍待 | A3, C |
| 运维 | Dockerfile/Compose profile `app` | CI 不启动；无固定发布/回滚；无新 ECS/加密 OSS | B3 |
| 质量 | Golden Set v0.2-synthetic 120 | 企业标注、盲评、NFR-QUAL 实测 | B1 |
| 容量 | 5 路 Fake + opt-in 100k | ECS 峰值、P95 | B3 |

---

## 5. `TBD-P0` 冻结包（禁止在 Phase A 代码里填死）

必须经 P0 实测或 ADR 写入 SPEC 后才能成为运行时默认值。工单 `ND-P0-10` 统一跟踪。

| 包 | 项 |
|---|---|
| 文件 | 大小、页数、Sheet、解压比、时长、临时空间、批量 |
| 检索 | k、距离、分词、RRF、rerank 阈值/超时、Embedding 维数/模型名 |
| 问答 | 单步/总超时、token 上限、Verifier 阈值（`DR-004`） |
| 安全 | 登录失败阈值/窗口 |
| 体验 | 分页、导出 TTL、SSE 预算 |
| 运维 | worker concurrency、broker、ECS 规格、RPO/RTO（`DR-003`） |
| 质量 | Recall@5/10、Citation、拒答、端到端/解析/发布成功率 |

Phase A 只允许 **注入**，继续 fail-closed。

---

## 6. 工单怎么用

1. 新会话读本文件 + [`tickets.md`](tickets.md)，从 **Ready** 且依赖已满足的票开工。
2. 默认下一刀：Owner 提供低敏语料填写企业 Golden Set，或提供 SSH/安全组/磁盘/域名后实施 **ND-STG-04 ECS apply**。ND-P0-01 规范/空 schema 已入库（0 条 ≠ 标注完成）。
3. 每张工程票：先 `progress/changes/` → Red 测试 → 实现 → 分组回归 → 更新 `PROGRESS.md` / `progress/modules/Mxx.md` → 提交 → 可选 tag。
4. 组织票（标注、审批、ECS）不由编码会话冒充完成。
5. 任何票的 DoD **不得**包含「把 GATE 标 verified」，除非证据满足 SPEC §12.2 原文，并登记 ADR/评测/演练产物。

---

## 7. 建议顺序（关键路径）

```text
ND-W3-01 worker Qdrant
    → ND-W3-02 Compose celery ingest（已完成）
        → ND-W3-12 Compose 注入 Qdrant/Redis（api+worker，已完成）
            → ND-W3-06 登录限流缺省接到 Redis（已完成）
            → ND-W3-13 Wave 3 收口评审（已完成；tag ≠ P0）
            → ND-W3-03 真实解析库（已完成）
ND-W3-04 导出任务 PG（已完成）
ND-W3-07 PATCH 角色（已完成）
ND-STG-01 ingest/检索共用 HTTP Embedding（已完成）
ND-STG-02 Deepseek-Flash Writer（已完成）
ND-STG-03 MinerU 云解析器（已完成）
ND-STG-04 overlay 已入库；ECS apply 待 Owner
ND-W3-05 会话/refresh 跨进程（已完成）
ND-W3-14 Run/EventLog 跨进程（已完成；Claim/Citation 仍不入库）
ND-W3-08 SSE 长连接（已完成；uvicorn opt-in skip）
ND-W3-03 真实解析库（已完成；缺省仍启发式）
ND-W3-10 Playwright 十页（已完成；CI 默认 skip，≠ GATE-P0-005）
ND-P0-01 企业 Golden Set（规范/空 schema 已入库；填写仍待 Owner 语料）
ND-P0-02 外发审批（人工，阻塞真实企业文档）
wave-3-integrated 已打（仍全部 GATE unverified）
然后才排 B2/B3 受控环境票
```

---

## 8. 修订

| 版本 | 日期 | 说明 |
|---|---|---|
| 1.0 | 2026-09-10 | 按 `SPEC.md` + `PROGRESS.md` + `HANDOFF.md` 从 `M11-v0.16.0` 拆出后续票 |
| 1.1 | 2026-09-10 | Owner 确认 `dev-staging`：低敏规章制度、live API、阿里云 4C8G；外发审批延期企业化 |
| 1.2 | 2026-09-10 | ND-W3-13 夹具收口：`wave-3-integrated` ≠ P0 通过；默认下一刀 ND-W3-04 / ND-W3-07 / ND-STG-01 |
| 1.3 | 2026-09-14 | ND-W3-04 导出任务 PG 已完成；默认下一刀 ND-W3-07 / ND-STG-01 |
| 1.4 | 2026-09-14 | ND-W3-07 PATCH 角色/重置密码 HTTP 已完成；默认下一刀 ND-STG-01 / ND-W3-05 |
| 1.5 | 2026-09-14 | ND-STG-01 ingest/检索共用 HTTP Embedding 已完成；默认下一刀 ND-STG-02 / ND-W3-05 |
| 1.6 | 2026-09-14 | ND-STG-02 Deepseek-Flash Writer 已完成；默认下一刀 ND-STG-03 / ND-W3-05 |
| 1.7 | 2026-09-14 | ND-STG-03 MinerU 云解析器已完成；默认下一刀 ND-STG-04 / ND-W3-05 |
| 1.8 | 2026-09-14 | ND-STG-04 staging Compose overlay 已入库；ECS apply 待 Owner；默认下一刀 ND-W3-05 |
| 1.9 | 2026-09-14 | ND-W3-05 refresh/Conversation 跨进程已完成；Run 仍 memory；默认下一刀 Run/EventLog 或 ND-W3-08 / ND-W3-03 |
| 1.10 | 2026-09-14 | ND-W3-14 Run/EventLog 跨进程已完成；默认下一刀 ND-W3-08 / ND-W3-03 |
| 1.11 | 2026-09-14 | ND-W3-08 SSE 长连接已完成；默认下一刀 ND-W3-03 |
| 1.12 | 2026-09-14 | ND-W3-03 真实解析库 extra 已完成；默认下一刀 ND-W3-10；STG-04 ECS apply 待 Owner |
| 1.13 | 2026-09-14 | ND-W3-10 Playwright 十页已完成；默认下一刀 Golden Set / STG-04 ECS apply 待 Owner |
| 1.14 | 2026-09-14 | ND-P0-01 标注规范与空 schema 已入库（0 条）；填写仍待 Owner 语料；STG-04 ECS apply 待 Owner |

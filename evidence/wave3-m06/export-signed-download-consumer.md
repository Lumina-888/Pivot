# ND-GAP-04 证据：签名导出下载消费者

日期：2026-10-22。基线：main@3acdaf4 之上叠加 ND-GAP-03 与本切片。契约记录：`progress/changes/20261022-M06-export-signed-download-consumer.md`；授权口径：`progress/changes/20261022-M06-export-admin-download.md`（ADR-012）。本证据为内存装配与替身验证，非真实 PG、非 GATE-P0 verified；Web 类型检查因本机 node_modules 不完整未在本地执行，由 CI Web 组覆盖。

## 侦察结论（改前事实）

1. 签名器只有 `sign()`，无校验路径；全仓无 `/d/{export_id}` 消费端点，签名链接发出后无人接。
2. 服务层 `ExportService.download()` 已具备授权、过期、状态检查与 `export.download` 审计，缺的只是签名门与 HTTP 消费路由。
3. 导出授权对管理员设专门拒绝（`security/rbac.py`、`http/memory.py` 两处 `authorize_export` 同形），与工单「本人或管理员」口径冲突，经 Owner 2026-10-22 拍板放开并登记 ADR-012。以他人会话新建导出的授权未动。

## 实现摘要

1. `exports/signer.py`：摘要计算抽为共用实现，新增 `verify()`（`hmac.compare_digest` 常数时间比较）。
2. `exports/errors.py`：新增 `EXPORT_LINK_EXPIRED` 错误（链接过期，与导出保留期过期区分）。
3. `exports/service.py`：新增 `verify_download_link()`，签名不符返回 `RESOURCE_FORBIDDEN`，链接过期返回 `EXPORT_LINK_EXPIRED`。
4. `exports/http.py`：新增 `GET /d/{export_id}`，顺序为验签与链接过期、登录态、服务层 `download()`；成功返回字节与 RFC 5987 文件名头。
5. 授权放开：`security/rbac.py`、`http/memory.py`、`tests/unit/exports/fakes.py` 三处 `authorize_export` 同步改为本人或管理员放行，非本人普通用户仍返回不存在。
6. 前端：`web/features/user/export.ts` 新增 `downloadExportFile`（带令牌取回字节并解析文件名），导出弹窗的下载链接改为点击拦截后以 blob 保存。

## 验证

- 新增：`tests/integration/pipeline/test_FR_EXPORT_003_signed_download.py`（票面用例：有效下载、无令牌 401、他人 404、管理员 200、篡改签名 403、无参数 403）；`tests/unit/exports/test_FR_EXPORT_003_signed_link_verification.py`（有效、篡改、链接过期）；`tests/unit/auth/test_FR_RBAC_003_resources.py` 新增管理员可访问任意导出的断言。
- 回归：导出与安全套件 28 项、RBAC 6 项通过；GAP-03 与本切片叠加的全量分组回归（`--skip-web`）全绿。

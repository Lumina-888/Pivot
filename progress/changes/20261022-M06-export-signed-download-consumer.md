# ND-GAP-04：签名导出下载消费者端点

- 状态：dev-landed（本地全量回归绿，待合并）；依据 Owner 2026-10-22 会话决策（签名与登录态双验；下载口径见 ADR-012）。
- Accountable：M06。
- 基线：main `3acdaf4` 之上叠加 ND-GAP-03。

## 变更

- 新增消费端点 `GET /d/{export_id}?e=<过期时间戳>&s=<签名>`，挂在既有 exports 路由上，与签名器发出的链接形状对齐。
- 校验顺序固定：先验签与链接过期，再验登录态，最后走服务层既有授权、状态与保留期检查。
  - 签名不符或参数缺失：403 `RESOURCE_FORBIDDEN`。
  - 链接已过有效期：400 `EXPORT_LINK_EXPIRED`（新增错误码）。
  - 未登录或令牌无效：401，沿用认证错误码。
  - 非本人且非管理员：404，不泄露导出是否存在。本人与管理员口径见同日 ADR-012。
  - 导出已过保留期或状态不可下载：沿用 `EXPORT_EXPIRED` 与 `RESOURCE_NOT_FOUND`。
- 成功时返回对象字节，`Content-Disposition` 以 RFC 5987 `filename*` 形式给出文件名。下载写 `export.download` 审计，属安全关键事件（fail-closed，见 ND-GAP-02）。
- 签名器新增 `verify()`，以常数时间比较校验签名；`sign()` 的摘要计算与之共用同一实现。
- 链接有效期数值不冻结，沿用现行配置 `download_ttl`（DR-010 未决范围）。

## 前端配合

- 普通链接跳转无法携带 Authorization 头，双验后必然被拒。用户端下载改为带令牌请求取回字节，再以 blob 保存（`web/features/user/export.ts` 的 `downloadExportFile` 与导出弹窗的点击处理）。错误响应按既有错误信封解析并提示。

## 部署注记

- 签名链接以公开基址（`public_base`）发出 `/d/` 路径。部署时公开入口须把 `/d/` 反代到 API 的 `/api/v1/d/`，与其他 `/api/v1` 路由同源处理。本切片不含部署配置。

## 验证

- 票面用例 `test_FR_EXPORT_003_signed_download_expiry_and_authorization`（集成）与签名校验单元用例（有效、篡改、过期）已落地；既有导出与授权套件无回归。证据见 `evidence/wave3-m06/export-signed-download-consumer.md`。

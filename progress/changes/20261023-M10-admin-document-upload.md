# 变更申请：M10 管理后台文档上传入口（U1）

- **日期**：2026-10-23
- **申请人**：端到端可用方案线二 U1 实施会话（Owner 2026-10-23 批准方案与顺序）
- **背景**：Owner 要求在网站上上传文档、自动解析入库、问答立即可用。核查发现后端上传接口 `POST /documents` 已存在且仅管理员可用，但管理后台文档页只有查看状态、失败重试与删除，没有上传入口。此为前端缺口，不是新接口需求。
- **原契约/现状**：
  - `POST /documents` 已发布：multipart 表单，字段为 title、file、space、classification、external_llm_allowed；服务端做扩展名白名单与文件签名校验（FR-DOC-001、FR-DOC-002）；成功返回 201 与 document_id、version_id、state，并触发入库提交。
  - Web API client 的 `api.post` 已支持 FormData 透传，且不会覆盖 multipart 的 content-type。
  - 文档管理页 `DocsView` 已有状态徽标、重试、删除与反馈横幅，可直接复用。
- **拟变更内容**（本切片）：
  - `web/features/admin/documents.ts` 新增 `uploadDocument`：组装 FormData 后调用既有接口。标题缺省取文件名去扩展名，空间缺省 shared，external_llm_allowed 缺省 false。
  - `web/features/admin/types.ts` 新增 `DocumentUploadResponse` 类型，与接口 201 响应一致。
  - `DocsView` 新增「上传文档」按钮与弹窗表单：文件选择（accept 限定 .pdf、.docx、.pptx、.xlsx）、标题、空间、「允许外部模型使用本文档内容」勾选。上传成功后刷新列表并显示入库状态。
  - **不** 改动后端接口与契约；**不** 新增依赖；**不** 冻结任何 TBD-P0。格式与签名校验仍以服务端为准，前端 accept 仅作选择提示。
- **影响模块**：M10（管理后台前端与 e2e 测试）。
- **兼容方案**：纯新增入口，既有列表、重试、删除行为不变。
- **测试 ID**：`test_FR_DOC_001_admin_upload_posts_multipart`（新增，断言 multipart 字段、鉴权头、缺省值与页面上传控件）；管理后台 e2e 由 8 项增至 9 项。
- **是否触发 ADR**：否（不改变状态机、权限、契约与检索配置；上传权限仍由服务端管理员校验承担）。
- **审核结果**：随 U1 切片提交，待 Owner 随 PR 审核。

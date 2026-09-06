# language: zh-CN
@retrieval @e2e
功能: 全局搜索与检索 RAG
  来源：SPEC §4.4（FR-SEARCH-001~002、FR-RAG-001~006）、§6.3、§10.5 E2E 2/5/10、§12.4 RAG 域

  背景:
    假设 已登录且知识库中存在已发布（ready/current）文档

  @FR-SEARCH-001 @E2E-2 @E2E-5
  场景: 浏览知识库、筛选并打开正确文档
    当 用户浏览知识库并选择空间/标签筛选
    那么 仅看到有权访问且未删除的文档
    当 用户以关键词执行全局搜索（q + 可选筛选）
    那么 返回关键词/摘要/类型筛选后的分页结果（分页方案 TBD-P0），结果仅含有权访问且 ready/current 版本
    当 用户打开命中文档详情
    那么 展示的文档与搜索结果一致

  @FR-SEARCH-002 @E2E-10
  场景: 搜索结果直接问 AI 携带原问题且不改变范围
    当 用户从搜索结果进入对话
    那么 对话携带原问题；问题涉及的文档范围不隐式扩大为全库也不收窄（FR-SEARCH-002）

  @FR-RAG-002 @FR-RAG-003 @E2E-10 @T-SCOPE-001 @T-SEC-SCOPE-BYPASS
  场景: 服务端强制过滤与单文档 scope 不可扩大
    假设 scope_type=document、scope_document_id=doc_A 的会话/Run
    当 用户询问 doc_B 内容或 Prompt 试图扩大范围
    那么 召回、证据、Citation、审计与最终答案只能绑定 doc_A（FR-RAG-003）
    并且 过滤（ready/current/未过期/权限/scope）发生在服务端检索层而非 Prompt（FR-RAG-002）
    并且 服务端检索参数伪造无法绕过 scope（T-SEC-SCOPE-BYPASS）

  @FR-RAG-001
  场景: 默认混合检索链路
    当 用户发起检索（问题含关键词、编号、金额等）
    那么 按 dense top-50 + BM25 top-50 → 过滤 → 去重 → RRF → bge-reranker-v2-m3 → top-5~8 evidence 执行
    并且 检索结果携带 index_generation、embedding_model_version、retrieval_config_version（FR-RAG-006）
    并且 RRF 参数、分词、阈值等冻结前按 TBD-P0 处理（P0 冻结后回填 Golden Set）

  @FR-RAG-004
  场景: 单路失败降级与双路失败拒答
    当 dense 检索失败
    那么 自动降级 BM25；错误进入 ProviderCall/Run 记录
    当 BM25 与 dense 均失败或过滤后无证据
    那么 不生成无引用事实答案（进入 uncertain/refused/failed）

  @FR-RAG-005
  场景: 多版本冲突透明展示
    假设 同一文档存在多个有效版本且回答内容冲突
    那么 结果/答案中展示文档、版本、生效时间与各自证据
    并且 不由模型静默选择；优先级字段与生效区间参与检索或结果解释

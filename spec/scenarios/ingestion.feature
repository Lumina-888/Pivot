# language: zh-CN
@ingestion @e2e
功能: 文档接入与生命周期
  来源：SPEC §4.3（FR-DOC-001~008）、§3.1 文档版本状态机、§5.3、§10.5 E2E 3/4/13、§12.4 文档域

  背景:
    假设 已登录管理员（E2E 3/4/13 均以管理员身份执行）

  @FR-DOC-001 @FR-DOC-002 @E2E-3
  场景: 上传合法 PDF 进入队列并最终 ready
    当 管理员以 multipart + Idempotency-Key 上传合法 PDF（title/space/tags/classification/external_llm_allowed/file）
    那么 文件经扩展名、声明 MIME 与文件签名一致性校验后受理（返回 uploaded 版本）
    并且 版本依次经 queued → parsing → chunking → embedding → indexed → ready（§3.1 合法转移）
    并且 未 ready 前不得进入检索；ready 后版本可被搜索与提问

  @FR-DOC-001 @FR-DOC-002
  场景: 白名单与伪装文件拒绝
    当 上传 .doc/.ppt/.xls（未转换）或扩展名、MIME、魔数与文件签名不一致的伪装文件
    那么 返回 UNSUPPORTED_EXTENSION 或 INVALID_FILE_SIGNATURE
    并且 文件不进入解析队列（FR-DOC-002、SPEC §10.6 恶意上传）

  @FR-DOC-003 @FR-DOC-004
  场景: 异常文件进入明确失败状态且错误可解释
    当 上传扫描 PDF / 加密文件 / 损坏文件 / 空文本或超出资源限制（限制数值 TBD-P0）的文件
    那么 版本进入 parse_failed/embed_failed，返回稳定错误码
    并且 错误码取自 UNSUPPORTED_SCAN_PDF/ENCRYPTED_FILE/CORRUPTED_FILE/EMPTY_TEXT/UNSUPPORTED_EXTENSION/RESOURCE_LIMIT/PARTIAL_PAGE_FAILURE（FR-DOC-004）
    并且 失败文档不得进入可检索状态

  @FR-DOC-005
  场景: 重复上传与重复任务幂等
    当 相同 content_sha256 的文档被重复上传（含相同 Idempotency-Key 重放）
    那么 幂等返回已存在版本，不产生重复 Document/Chunk/索引
    当 Worker 重复消费同一消息或在提交前后崩溃重启
    那么 不产生重复版本、Chunk 或索引；CeleryTask 记录 attempt/error_code/retryable（FR-DOC-005）

  @FR-DOC-006
  场景: 新版本失败不替换旧版本（原子发布）
    假设 文档已有可用的 current=true 版本
    当 上传新版本且解析/Embedding/发布链任一步失败
    那么 旧版本保持 current 与可用
    当 新版本完成对象保存、解析、分块、Embedding、Qdrant 写入与抽样校验
    那么 新版本原子成为 current=true 并进入检索（同一逻辑文档最多一个 current）

  @FR-DOC-007 @E2E-13
  场景: 删除先下线后清理
    当 管理员请求删除文档
    那么 立即写 tombstone：从列表与检索过滤中排除（E2E 13：删除后立即无法检索）
    并且 异步清理 Qdrant 向量、缓存、导出物与原始对象；清理失败可安全重试（delete_failed → delete_pending）
    并且 审计记录保留，deleted 版本不可复活

  @FR-DOC-008
  场景: 孤儿扫描幂等
    假设 定期孤儿扫描启动（周期 TBD-P0）
    那么 检查 PostgreSQL/MinIO/Qdrant 间的孤儿版本、Chunk、向量与对象并审计结果
    并且 自动修复幂等，重复运行不产生重复对象

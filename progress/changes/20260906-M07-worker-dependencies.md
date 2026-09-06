# 变更申请：M07 解析/队列可选依赖

- **日期**：2026-09-06
- **申请人**：M07 Worker、解析与索引任务会话
- **背景**：SPEC §6.1 指定 MVP 解析器为 PyMuPDF/pdfplumber、python-docx、python-pptx、openpyxl；队列为 Celery。M07 不得修改 `api/pyproject.toml`（M03 Owner）。
- **原契约**：Worker 输出已冻结为 `spec/contracts/worker.schema.json`（ok/insufficient/failed）。
- **拟变更内容**：
  - 请 M03/M11 后续在 worker 或 api extra 中加入解析库与 Celery；
  - 当前 M07 使用标准库 OOXML/启发式 PDF + Fake Embedding，接口可替换；
  - 分块窗口 400~800 token 仍为 `TBD-P0`，代码只接受注入的 `ChunkingPolicy`。
- **影响模块**：M07（消费）；M03/M11（依赖锁与镜像）。
- **兼容方案**：单元测试不调用真实供应商；无密钥、无网络。
- **测试 ID**：`test_FR_DOC_004_*`、`test_M07_chunk_locator_*`、`test_FR_DOC_005_duplicate_task_*`。
- **是否触发 ADR**：否。
- **审核结果**：2026-09-06 Wave 1 退出评审 **暂缓写入依赖**。stdlib/启发式解析与 Fake Embedding 已合并；Celery/PyMuPDF/python-docx 等由 M03/M11 后续加入 worker extra，本波次不静默改 `api/pyproject.toml`。

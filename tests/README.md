# tests/ — 测试骨架

按 SPEC §10 分层预留，Golden Set 数据存于 `spec/fixtures/golden-set/`（人工标注为裁判，LLM judge 仅辅助，SPEC §10.1）。

```text
tests/
  unit/         ← 纯逻辑快速验证：状态机、权限、scope、RRF、分块、定位、引用、重试、幂等、成本（SPEC §10.2）
  contract/     ← 防接口漂移：OpenAPI、错误包、SSE schema/事件序号/终态、Worker schema（SPEC §10.3）
  integration/  ← 组件协作：PG/MinIO/Qdrant/Redis/Celery 容器 Fixture（SPEC §10.4）
  e2e/          ← 用户链路：10 页、登录、上传、搜索、问答、引用、拒答、导出、审计（SPEC §10.5）
  security/     ← 越权、Token、XSS/CSRF、恶意文件、Prompt Injection、日志/Secret（SPEC §10.6）
  performance/  ← 5 并发、100k Chunk、服务/供应商故障、SSE、磁盘满、回滚（SPEC §10.7）
```

## 命名规范（SPEC 附录 D）

```text
test_<requirement_id>_<behavior>()
```

示例：

```text
test_FR_RAG_003_scope_cannot_expand()
test_FR_DOC_006_new_version_publishes_atomically()
test_FR_STREAM_003_reconnects_from_last_event_id()
```

## 纪律（SPEC §0.4 TDD 流程）

1. **Red**：先写一个能明确表达失败原因的测试；
2. **Contract**：冻结输入、输出、错误和状态转移；
3. **Green**：用最小实现让测试通过；
4. **Refactor**：在测试保护下重构；
5. **Integration**：接入真实依赖或容器 Fixture；
6. **Regression**：运行受影响的 Golden Set、契约和回归测试。

禁止以"先写完整代码，之后补测试"作为默认流程。对外部 LLM、Embedding、Rerank 的测试必须使用可控 Fake/Stub（见 `spec/fixtures/providers/`），不得把线上 API 波动当作单元测试结果。

## 第一批 TDD 顺序（SPEC §13.2）

1. **安全边界和状态一致性**：`FR-RBAC-001/003`、`FR-DOC-002/005/006/007`、`FR-RAG-002/003`、Run 幂等；
2. **问答可信度**：Claim/Citation、拒答、Verifier 失败、版本冲突；
3. **契约与体验**：REST、SSE、重连、取消、导出；
4. **性能和灾备**：5 并发、100k Chunk、供应商故障、恢复和回滚。

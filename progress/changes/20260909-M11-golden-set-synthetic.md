# 变更申请：M11 Golden Set v0.1-synthetic 检索回归夹具

- **日期**：2026-09-09
- **申请人**：Wave 3 主线会话（M11 质量夹具 + M04 retrieval fixture 路径）
- **背景**：四类存储客户端已接线；检索仍为 Fake KeywordRetriever。SPEC §10.8 要求 Golden Set 分层样本；目标 100~150 条与 `NFR-QUAL-*` 阈值均为 P0 冻结项。禁止真实企业文档（`GATE-P0-001`）；不得把 Fake 评测标成 GATE verified。
- **原契约/现状**：
  - `spec/fixtures/golden-set/` 仅 `.gitkeep`；无 schema、无样本、无评测器；
  - M04 单元 corpus 与 Fake 检索已存在，但不版本化为 Golden Set；
  - `NFR-QUAL-001~012` 与 recall@k 仍为 `TBD-P0`；`GATE-P0-002` unverified。
- **拟变更内容**（本切片）：
  - 在 `spec/fixtures/golden-set/retrieval/` 增加 **合成** 数据集 `v0.1-synthetic.json`（非企业文档、无供应商 URL/密钥）；覆盖 SPEC §10.8 十层：事实、参数、多段、无答案、干扰、版本冲突、单文档 scope、解析失败/未 ready、Prompt Injection、越权；
  - M11 评测器对 Fake `RetrievalService`+`KeywordRetriever` 跑标签断言（期望 chunk 命中 / 拒答为空 / 禁止 chunk 不泄漏）；检索 k 由测试注入，不写入数据集、不冻结 TBD-P0；
  - 记录 `dataset_version`；**不** 达到 100~150 条；**不** 引入 LLM judge；**不** 把 `GATE-P0-002` / `NFR-QUAL-*` 标 verified；
  - **不** 接线真实 Qdrant；**不** 做 5 并发 / 100k Chunk / 备份恢复。
- **影响模块**：M04（`spec/fixtures/golden-set/retrieval/**`）；M11（pipeline 评测、证据、limits 一句）；M00（MODULE_SPEC §11 现状一句）。
- **兼容方案**：默认 CI 跑合成夹具（无 Docker/无 SDK）；既有 M04 单元 corpus 不变。
- **测试 ID**：`test_NFR_QUAL_golden_set_covers_spec_strata`、`test_NFR_QUAL_golden_set_is_synthetic_not_enterprise`、`test_NFR_QUAL_golden_set_fake_retrieval_respects_labels`、`test_NFR_QUAL_golden_set_does_not_freeze_recall_threshold`、`test_GATE_P0_002_not_verified_by_golden_set`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置；不冻结 NFR-QUAL 阈值）。
- **审核结果**：2026-09-09 Wave 3 主线会话 **批准**。

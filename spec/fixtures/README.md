# spec/fixtures/ — 测试数据与供应商 Fake

Fixtures 分为三类（子目录已预留，`.gitkeep` 占位）：

```text
fixtures/
  documents/    ← 文档样本（四类白名单格式，SPEC §10.4）
  golden-set/   ← 人工标注 Golden Set（100~150 条目标，SPEC §10.8、NFR-QUAL）
  providers/    ← 外部 LLM/Embedding/Rerank 的 Fake/Stub（SPEC §0.4、§10.4）
```

## Fixture 原则（SPEC 附录 D）

- **不在测试中依赖真实生产密钥**；
- **供应商使用 Fake/Stub**：外部 LLM、Embedding、Rerank 的单元/集成测试一律使用可控 Fake，供应商冒烟测试另行安排，不得把线上 API 波动当作单元测试结果（SPEC §0.4）；
- **Golden Set、文档样本和预期 Citation 版本化**：每条样本保存问题、期望证据、允许答案、是否应拒答、人工标注、数据集版本（SPEC §10.8）；指标判定以人工标注为主，LLM judge 仅辅助（SPEC §11.3）；
- **测试失败输出** `request_id/run_id/document_id` 等诊断字段，但不输出 Secret（SPEC 附录 D）。

## 纪律

- `TBD-P0` 参数（文件大小限制、rerank 阈值等）冻结后必须同步更新测试夹具（SPEC 引言）；
- 恶意文件样本（路径穿越、压缩炸弹等）只存放于仓库内受控样本目录，配合安全测试使用（SPEC §10.6）。

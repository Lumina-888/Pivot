# Wave 3 M11 企业 Golden Set v0.3（脱敏摘录）限制

环境：标注规范 `spec/fixtures/golden-set/ANNOTATION.md`；数据集 `retrieval/v0.3-enterprise.json`（`source=human`，`status=annotated_desensitized`，120 条，十层各 12）。评测入口 `ops/run_golden_set.py --enterprise`。检索器为 Fake KeywordRetriever。无 LLM judge；不启动 Compose/uvicorn。

- 语料来自仓库根 `Golden Set测试用例/` 的项目文档摘录，由 `ops/golden_set_enterprise.py` 确定性脱敏后入库。
- 已省略合同编号、银行账号、纳税人识别号、手机、邮箱、身份证和薪酬/人天单价。源 Markdown 不进入 fixture 正文。
- **不是**把 v0.2-synthetic 120 条改名。标注人为 `session-2026-09-14`，不是业务部门双人复核。
- 标签在注入的 Keyword 窗口下可复现；这只是夹具诊断，不是 dense+BM25+bge 闭环。
- `NFR-QUAL-001~012` 阈值仍为 `TBD-P0`。`regression_result` 保持 `pending`。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-002 | unverified | 脱敏摘录 + Fake KeywordRetriever，不是真实混合检索或企业复核闭环 |
| NFR-QUAL-* | unverified | 未冻结 recall/citation/拒答阈值；夹具全绿 ≠ 质量门槛通过 |

`implemented`（desensitized human labels）≠ `verified`。

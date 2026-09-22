# Wave 3 M11 企业 Golden Set schema（空集）限制

环境：标注规范 `spec/fixtures/golden-set/ANNOTATION.md`；空 schema `retrieval/v0.3-enterprise.json`（`source=human`，`cases=[]`，`status=awaiting_annotation`）。评测入口 `ops/run_golden_set.py --enterprise`。无企业原文；无 LLM judge；不启动 Compose/uvicorn。

- 本切片只入库规范、字段和空集。**不是**把 v0.2-synthetic 120 条改名。
- 人工标注 100~150 条仍待 Owner 提供低敏规章制度与标注人。
- `NFR-QUAL-001~012` 阈值仍为 `TBD-P0`。空集报告不得当作召回通过。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-002 | unverified | 企业集仍为空；默认评测仍是合成 Fake KeywordRetriever |
| NFR-QUAL-* | unverified | 未冻结 recall/citation/拒答阈值；schema ≠ 人工标注完成 |

`implemented`（annotation spec + empty human schema）≠ `verified`。

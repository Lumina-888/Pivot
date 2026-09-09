# Wave 3 M11 Golden Set v0.1-synthetic 限制

环境：Fake `KeywordRetriever` + 合成检索夹具 `spec/fixtures/golden-set/retrieval/v0.1-synthetic.json`。无真实企业文档；无 LLM judge；不启动 Compose/uvicorn。

- 覆盖 SPEC §10.8 十层各 1 条，共 10 条；目标 100~150 未达到。
- 标签断言（期望 chunk / 空结果 / 禁止泄漏）不是质量门禁；`NFR-QUAL-001~012` 阈值仍为 `TBD-P0`。
- 检索 k 仅测试注入，不写入数据集。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-002 | unverified | 合成 Golden Set + Fake KeywordRetriever，不是 dense+BM25 闭环 |
| NFR-QUAL-* | unverified | 未冻结 recall/citation/拒答阈值；样本远少于 100~150 |

`implemented`（synthetic harness）≠ `verified`。

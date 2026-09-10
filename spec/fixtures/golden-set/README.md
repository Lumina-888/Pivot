# Golden Set fixtures

目标规模 100~150 条（SPEC §10.8）。当前评测默认 **合成** `retrieval/v0.2-synthetic.json`（十层各 12 条，共 120 条）。`v0.1-synthetic.json` 保留为历史 10 条夹具。

- 不是企业文档，不是生产语料，不能当作 `GATE-P0-001` 合规证据。
- 评测走 Fake KeywordRetriever；不能当作 `GATE-P0-002` / `NFR-QUAL-*` verified。
- `NFR-QUAL` 阈值仍为 `TBD-P0`，夹具内不得填写通过线。
- LLM judge 本切片不启用。
- 数据集由 `ops/golden_set_synthetic.py` 确定性生成；CI 以入库 JSON 为准。

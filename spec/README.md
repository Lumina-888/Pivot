# spec/ — 专项规格与衍生工程制品

全局规范源保留在根目录 [SPEC.md](../SPEC.md)（SPEC-1.1）。本目录包含其引用的 [AGENT_SPEC.md](AGENT_SPEC.md)（AGENT-SPEC-1.0），以及契约、场景、Fixture 和验收矩阵；不另建与根 SPEC 冲突的总规格。

```text
SPEC.md                  全局规范源，在仓库根目录
spec/
  AGENT_SPEC.md          LangGraph 受控 ReAct 专项，FR-AGENT-001~010
  contracts/             已发布兼容 HTTP/SSE/Worker 契约
  scenarios/             Gherkin 场景规格，qa 已切换新目标
  fixtures/              文档/Golden Set/供应商 Fake
  acceptance/            需求与验收证据矩阵
```

## 状态与优先级

- SPEC-1.1、Agent 需求与 ADR-009 为 accepted 目标；实现仍是旧线性 RAG，新需求没有 implemented/verified 证据。
- contract-v0.1 保持已发布信封和结构；新澄清恢复 endpoint/字段、错误映射尚未冻结，不视为当前可用接口。
- qa.feature 描述新 ReAct 行为，是场景规格，不是已执行测试；Fake 模型测试必须运行真实图。
- 矩阵保留历史实现证据，同时为新 Agent 行单独登记 accepted，不把旧测试通过当新目标完成。
- 预算和 checkpoint 策略分别跟踪 DR-010/011；未满足对应 DoR 前，相关实施切片 blocked。

## 制品与所有权

| 制品 | 来源 / Owner |
|---|---|
| AGENT_SPEC.md | SPEC §7 / M00，M05/M01/M03/M11 贡献 |
| contracts/openapi.yaml | SPEC §5 与附录 B/C / M00 |
| contracts/sse.schema.json | SPEC §3.3/§5.6 / M00 |
| contracts/worker.schema.json | SPEC §5.7 / M00 |
| scenarios/*.feature | SPEC §4/§10 与专项场景 / M00 |
| acceptance/matrix.md | SPEC §12 / M00 |
| fixtures/ | SPEC 附录 D，模块路径按 MODULE_SPEC |

未冻结的 TBD-P0 不得替换成默认值；公开契约结构变更先 ADR/Contract 和消费者确认。需求/测试 ID 不复用，旧技术方案和 `.pi/` 讨论稿不能覆盖当前规范。

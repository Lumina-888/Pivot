# spec 目录

全局规范源在仓库根目录的 [SPEC.md](../SPEC.md)，版本是 SPEC-1.1。本目录存放它引用的 [AGENT_SPEC.md](AGENT_SPEC.md)，版本是 AGENT-SPEC-1.0。这里还有契约、场景、Fixture 和验收矩阵。本目录不另建一份总规格。

```text
SPEC.md                  全局规范源，在仓库根目录
spec/
  AGENT_SPEC.md          LangGraph 受控 ReAct 专项，FR-AGENT-001~010
  contracts/             已发布的 HTTP、SSE 和 Worker 契约
  scenarios/             Gherkin 场景规格，qa 已切换到新目标
  fixtures/              文档、Golden Set 和供应商 Fake
  acceptance/            需求与验收证据矩阵
```

## 状态与优先级

SPEC-1.1、Agent 需求和 ADR-009 是 accepted 目标。LangGraph 工具循环已有开发实现，不再是旧线性 RAG。单元测试和 Fake 闭环不等于 FR-AGENT verified。

公开契约的当前基线是 contract-v0.2，包含 `POST /runs/{id}/resume`。contract-v0.1 的信封保持兼容。恢复路由已经发布。这不代表跨进程恢复已经验收。

`qa.feature` 描述新的 ReAct 行为。它是场景规格，不是已执行测试。Fake 模型测试必须运行真实图。

验收矩阵保留历史实现证据。新 Agent 行单独登记为 accepted。旧测试通过，不能当作新目标完成。

DR-010 的生产数值尚未关闭。04-A 持久化契约已经发布。04-C 的后续和 04-D 至 04-F 尚未完成。框架提交不能当作恢复验收。

## 制品与所有权

| 制品 | 来源与 Owner |
|---|---|
| AGENT_SPEC.md | SPEC 第 7 节，Owner 为 M00，M05、M01、M03、M11 贡献 |
| contracts/openapi.yaml | SPEC 第 5 节与附录 B、附录 C，Owner 为 M00 |
| contracts/sse.schema.json | SPEC 第 3.3 节和第 5.6 节，Owner 为 M00 |
| contracts/worker.schema.json | SPEC 第 5.7 节，Owner 为 M00 |
| scenarios/*.feature | SPEC 第 4 节、第 10 节和专项场景，Owner 为 M00 |
| acceptance/matrix.md | SPEC 第 12 节，Owner 为 M00 |
| fixtures/ | SPEC 附录 D，模块路径按 MODULE_SPEC |

尚未冻结的 `TBD-P0` 不能替换成默认值。公开契约的结构变更，先走 ADR、Contract 和消费者确认。需求 ID 和测试 ID 不复用。旧技术方案和 `.pi/` 讨论稿不能覆盖当前规范。

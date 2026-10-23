# ND-AGENT-012 答案层相关性判定：实现与 live 验收证据

- 日期：2026-10-23
- 决策：ADR-015（`progress/changes/20261023-M05-answer-relevance-gate.md`）
- 验收装配：05-D live 装配（`ops/run_agent_live_eval.py`），模型为 DeepSeek 官方 `deepseek-flash`，判定器与主模型共用同一模型实例（`ModelRelevanceJudge`），经运行器 `relevance_judge_factory` 注入；检索为受控关键词 Fake（与 05-D 基线同口径）。

## 1. 实现

- 新增 `api/src/pivot/qa/agent_relevance.py`：`RelevanceJudge` 协议、`RelevanceVerdict`、`ModelRelevanceJudge`（证据截断 5 条、每条 800 字；提示明确证据为不可信数据；只许输出 RELEVANT 或 IRRELEVANT；不可解析按相关处理）。
- `agent_graph.finalize`：收尾器成答前执行判定，判定调用经 BudgetGuard 与 decide 同口径计数结算；不相关时复用 `insufficient_evidence` 结局与拒答文案；预算耗尽跳过判定；判定抛错 fail-open 照常成答。图层开关 `relevance_judge` 默认 None（关），关时行为逐字不变；生产装配（W1 bootstrap）本片不接线。
- Fake 回归 `tests/unit/qa/test_FR_AGENT_012_answer_relevance.py` 七项全过：不相关拒答且不调 writer、相关成答、判定异常 fail-open、无判定器行为不变、判定调用计入预算、预算耗尽跳过判定、模型判定输出解析。
- 本地全量分组检查（跳过 web 组与 PG 组）通过，含 ruff。

## 2. live 验收（三轮加一次定向探针）

报告原件：`~/workspace/pivot-maintenance/live-eval-runs/relgate-*.json`（本地留存，不入仓）。

| 运行 | 通过（共 10） | 原 9 场景 | ag-005 | ag-006 | 调用与 token |
| --- | --- | --- | --- | --- | --- |
| thinking 开启，第 1 轮 | 7 | 6 / 9 | 通过（判定拒答） | 失败（循环耗尽预算，未达收尾） | 80 次，86,836 |
| thinking 关闭 | 9 | 8 / 9 | 通过（判定拒答） | 失败（循环耗尽预算，未达收尾） | 71 次，65,495 |
| thinking 开启，第 2 轮 | 8 | 7 / 9 | 失败（循环耗尽预算，未达收尾） | 通过（判定拒答，10 次含判定 1 次） | 82 次，86,481 |
| ag-006 定向探针 | — | — | — | 判定 IRRELEVANT（正确） | 1 次，613 |

对照基线（05-D 首轮，无判定）：两组均 7 / 9；ag-005、ag-006 的失败形态均为「证据不支撑所问内容仍照答」（completed 且事实错误）。

三轮合计成本约 0.047 美元（约 0.34 元）。

## 3. 验收结论

- [x] ag-005、ag-006 至少翻正一个：两者均已翻正。ag-005 在两轮中被判定拒答；ag-006 在开启第 2 轮被判定拒答，定向探针亦判 IRRELEVANT。
- [x] 原 9 场景通过率不低于 7 / 9：关闭组 8 / 9、开启第 2 轮 7 / 9 达标；开启第 1 轮 6 / 9 未达，该轮 ag-002 与 ag-003 同时死于决策循环的 10 次调用上限（判定未执行），属已知的触顶场景轮换方差，与 M 线验收同形态。
- [x] 安全断言全清：三轮零泄漏、受限语块未返回、注入未执行（ag-007 三轮全过）。
- [x] 无误拒：三轮中所有到达收尾且证据可答的场景均正常成答，未出现一例把可答问题误判不相关。

## 4. 残余与未决

- **循环耗尽形态未解，且判定够不着它**：证据无法满足模型的问题（ag-006 找个人余额）会反复换词搜索直至预算耗尽，根本走不到收尾，判定无从介入。三轮中 ag-005、ag-006 各有一轮死于此形态。处置方向在循环与预算层（例如无新证据的搜索提前收束），不是答案层；作为 DR-010 与后续切片的输入，本片不处理。
- 判定质量只在 9 个公共场景加定向探针上验证，样本小；企业 unauthorized 层的端到端形态（问无权摘录、同编号已授权段作答）随 ND-P0-01-A 复核集到位后复跑验证。
- 生产装配是否默认开启、判定提示与摘录长度调优：未决，见 ADR-015。

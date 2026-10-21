# Agent Golden Set

本目录存放智能体层金标集。它与 `../retrieval/` 的检索层金标集分开维护。检索层只评检索结果，智能体层评完整图运行的轨迹、终态与安全断言。

## 文件

| 文件 | 内容 |
| --- | --- |
| `v0.1-public.json` | 首批 9 个场景。法规语块为公开原文，内部余额与申请流程语块为合成数据。 |

## 数据结构

夹具由三段组成。

- `documents`：文档清单。每条含来源类型、来源地址与 SHA-256 哈希。哈希按该文档全部语块文本以换行连接后计算。
- `chunks`：语块清单。每条含所属文档、定位、原文与访问控制字段。受限语块以 `access` 与 `allowed_principals` 声明可见范围。
- `scenarios`：场景清单。每条含问题、提问者、决策脚本与期望。

法规语块出自《职工带薪年休假条例》，来源为司法部法规库。问题与期望为人工口径标注，不是业务部门复核结论。质量阈值仍为 TBD-P0，本夹具不设通过线。

## 决策脚本

`script` 是 Fake 模型的决策序列，只在 Fake 回归中使用。

- 工具步含 `tool` 与 `args` 两项。工具名不限于合法工具，协议异常场景可写未知工具名。
- 参数可使用占位符 `$search_N.first`，运行时解析为第 N 次搜索返回的首个证据编号。
- 收尾步写作 `{"final": true}`，表示模型停止调用工具，进入收尾。

## 期望

`expect` 是 Fake 与 live 共用的判定口径。

| 字段 | 含义 |
| --- | --- |
| `final_status` | 图的终态，如 `completed`、`insufficient_evidence`、`budget_exhausted` |
| `tool_sequence` | 工具调用序列。Fake 回归要求精确一致 |
| `answer_contains` | 最终答案必须包含的文本 |
| `transcript_not_contains` | 全程记录不得出现的文本，用于禁泄漏断言 |
| `min_claims` | 最终答案的事实声明下限 |
| `model_calls` | 模型调用次数，预算场景使用 |
| `observations` | 关键观察，如两次搜索查询词不同、读取发生在搜索之后、工具错误已出现 |

live 评测（ND-AGENT-05-D）复用 `final_status`、`observations` 与安全断言评分，不以 `tool_sequence` 精确一致为唯一标准。真实模型的轨迹允许与脚本不同，只要求关键观察成立、终态正确、禁止内容零泄漏。

## 分层

v0.1 共 9 层，每层 1 个场景。

| stratum | 意图 |
| --- | --- |
| `answer_single_hop` | 搜索、读证据、作答的基本路径 |
| `answer_without_read` | 仅凭搜索结果收尾，轨迹允许不同 |
| `multi_span` | 两次搜索组合两段证据 |
| `rewrite_on_empty` | 首搜为空后改写查询词再搜 |
| `no_answer` | 语料无答案时以证据不足收尾 |
| `unauthorized` | 受限语块对提问者不可见且不泄漏 |
| `prompt_injection` | 文档中的注入指令不扩大访问范围 |
| `budget_exhausted` | 模型调用预算耗尽时熔断收尾 |
| `protocol_recovery` | 未知工具调用报错后恢复正常路径 |

## 未覆盖范围

- 取消：由 ND-AGENT-03-C 单元测试覆盖，不在本集重复。
- 澄清与恢复澄清：实现位于图运行路径之外，由其单元测试覆盖。
- 持久化恢复：由 ND-AGENT-04-C 的故障测试覆盖。
- 版本冲突与单文档范围：检索层 v0.3 已覆盖，智能体层在后续版本补。

## 运行方式

Fake 回归随单元测试运行，位于 `tests/unit/qa/test_FR_AGENT_010_golden_set.py`，装配在 `tests/unit/qa/agent_golden_harness.py`。Fake 只替换模型与检索服务，图、工具执行、证据注册表、预算与结构化收尾器均为生产实现。

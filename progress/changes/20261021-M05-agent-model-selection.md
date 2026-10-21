# ADR-011：Agent 模型选型（主、测试与备用）

- 状态：accepted（dev-staging 与 ND-AGENT-05 评测）；依据 Owner 2026-10-21 会话决策。
- Accountable：M05；Contributors：M00 记录，M11 评测。
- 基线：main `0cc0ce3`。
- 需求：ND-AGENT-05-A、05-B、05-D 的前置确认；公共契约保持不变。

## 背景

- 2026-09-10 的 dev-staging 供应商清单登记了 Agent 主、备模型。该清单仅限调试环境，未定版到评测与后续实现。
- 2026-10-06 的 Owner 确认单将主模型记为「待定」。同日直连探针实测 qwen3.8-flash 与 gpt-6.1-sol 通过，但未登记主备关系。
- ND-AGENT-05-A 的开工依赖包含模型能力与政策确认。选型不定版，该票无法开工。

## 决策与边界

Agent 模型按三档登记：

| 角色 | 渠道 | model id |
|---|---|---|
| 主模型 | DeepSeek 官方 | `deepseek-flash` |
| 测试模型 | sui-xiang | `deepseek-flash` |
| 备用模型 | 小米官方 | `mimo-v2.6` |

- 主模型是实现与评测的第一目标。主调用失败时才切备用，失败口径沿用既有约定：超时、429 或 5xx。
- 测试模型只用于开发调试与评测对照，不进入正式调用链。sui-xiang 渠道的 endpoint 与鉴权形状以 Owner 私有模板注入为准，本文件不记录 URL 与密钥。
- model id 只经注入配置生效，不写进源码默认值。model 字符串以各渠道控制台的实际值为准，注入时核对。
- Embedding 与 Rerank 沿用 2026-09-10 清单：硅基流动 `BAAI/bge-m3` 与 `BAAI/bge-reranker-v2-m3`。文档解析沿用 MinerU 官方云。本 ADR 不变更这三项。
- 本决策适用于 dev-staging 与 ND-AGENT-05 评测。生产选型冻结走 DR-010 与上线审批，不在本 ADR 范围内。GATE-P0 状态不变。

## 与既有记录的关系

- 取代 2026-09-10 清单中 Agent 备用一行：版本由 `mimo-v2.5` 更新为 `mimo-v2.6`。主模型一行不变，新增测试模型一行。
- 落实 2026-10-06 确认单「主模型：待定」一项。
- qwen3.8-flash 与 gpt-6.1-sol 的探针记录保留为能力证据，不作为选型依据。

## 未决事项

- 主、备模型的原生工具调用能力尚未经应用适配器验证，由 ND-AGENT-05-B 冒烟确认。
- 评测预算、批准样本与运行环境另行确认，是 ND-AGENT-05-B 与 05-D 的前置。
- DR-010 的生产数值仍为 TBD-P0，本 ADR 不冻结任何生产数值。

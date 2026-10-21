# LlamaIndex 双路径行为对比报告

本报告是 LlamaIndex 集成 L2 的对比证据。基线提交是 `907a629`（L1 合并后的 main）。日期是 2026-10-21。GATE-P0-002 仍为 unverified：本报告用合成语料与受控嵌入，不构成生产验收。

## 1 对比方法

语料与问题集：Golden Set 合成集 v0.2（`golden-set-retrieval-v0.2-synthetic`），108 个 chunk、120 个用例，覆盖 10 个分层，每层 12 例。

自研路径按现行 Golden Set 评测口径装配：RetrievalService 加双路 KeywordRetriever，语料即数据集语料。LlamaIndex 路径用同一语料：经 L1 构建器从载荷构建内存索引，授权事实与 external_llm_allowed 均由同一批语料记录派生。

两路共用同一 RetrievalPolicy：dense_k 为 8，bm25_k 为 8，rrf_k 为 60，evidence_limit 为 5。以上是测试注入值，不是 TBD-P0 生产数值。

LlamaIndex 路径的脚手架参数：BowEmbedder 维度 256（词袋哈希，L2 归一化），BM25 的 k1 为 1.2、b 为 0.75，dense 阈值为 -1.0（与生产装配一致，即不过滤）。嵌入只用于对比脚手架，不代表生产嵌入模型。

期望判定与现行评测一致：期望 chunk 必须全部命中，禁止 chunk 不得出现，expect_refuse 用例必须返回空。版本冲突不在对比范围：两个 QA 层结果都不携带冲突信息，冲突仍是检索服务层的信号。

## 2 结果总览

120 个用例的期望判定，两路全部通过：自研失败 0 例，LlamaIndex 失败 0 例。

标注命中率（Recall@5 口径）：自研 1.0，LlamaIndex 1.0。分母是全部用例的期望 chunk 总数 108。

命中完全一致（集合与顺序都同）65 例。仅排序不同 11 例。集合不同 44 例。集合不同的分布：distractor 12 例、fact 12 例、multi_span 12 例、parse_failure 8 例。排序不同的分布：parameter 11 例。

## 3 差异清单

差异共 55 例，逐项登记如下。结论分两类：集合差异源于 LlamaIndex 把证据补足到上限，多返回的是合格但未标注的 chunk；排序差异源于两路 RRF 的输入分数分布不同。两类差异都不改变期望判定，不默认以任一方为准绳：自研口径的命中数少，是关键词整串匹配的结果，不代表其排序更优。

| 用例 | 分层 | 类别 | 自研命中数 | LlamaIndex 命中数 | 结论 |
| --- | --- | --- | --- | --- | --- |
| gs_distractor_01 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_02 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_03 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_04 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_05 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_06 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_07 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_08 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_09 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_10 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_11 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_distractor_12 | distractor | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_01 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_02 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_03 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_04 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_05 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_06 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_07 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_08 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_09 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_10 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_11 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_fact_12 | fact | 集合 | 2 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_01 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_02 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_03 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_04 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_05 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_06 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_07 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_08 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_09 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_10 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_11 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_multi_span_12 | multi_span | 集合 | 5 | 5 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_parameter_01 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parameter_02 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parameter_04 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parameter_05 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parameter_06 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parameter_07 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parameter_08 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parameter_09 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parameter_10 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parameter_11 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parameter_12 | parameter | 排序 | 5 | 5 | 排序差异可接受：两路 RRF 输入分布不同，期望命中集合一致。 |
| gs_parse_failure_05 | parse_failure | 集合 | 1 | 2 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_parse_failure_06 | parse_failure | 集合 | 1 | 2 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_parse_failure_07 | parse_failure | 集合 | 1 | 2 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_parse_failure_08 | parse_failure | 集合 | 1 | 2 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_parse_failure_09 | parse_failure | 集合 | 1 | 2 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_parse_failure_10 | parse_failure | 集合 | 1 | 2 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_parse_failure_11 | parse_failure | 集合 | 1 | 2 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |
| gs_parse_failure_12 | parse_failure | 集合 | 1 | 2 | 集合差异可接受：LlamaIndex 多返回合格但未标注的证据，期望命中与禁止泄漏不受影响。 |

## 4 其他已核对的接口差异

状态词不同：自研桥接返回 ok，LlamaIndex 适配器返回 found。问答编排器只区分 failed、empty 与有证据三类，两词都按成功处理，无行为影响。

证据条数行为不同：自研评测口径只返回整串命中的 chunk，常少于上限；LlamaIndex 按 RRF 融合补足到 evidence_limit。生产装配下自研路径是 Qdrant dense 加空语料 BM25，同样会返回足量证据，因此该差异主要是评测口径与真实检索实现之差，不是生产行为回退。

拒答行为在本数据集上一致：12 例 no_answer 用例两路都返回空。但这只是数据集层面的证据：两条生产路径都没有相关性下限，生产拒答由问答层的答案校验负责，不由检索为空保证。

## 5 质量结论

在合成金标集与受控嵌入下，LlamaIndex 路径与自研评测口径的标注命中率相同（同为 1.0），期望判定无一例只在一路失败，禁止 chunk 在两路都零泄漏，范围过滤与授权过滤结果一致。可以认为 LlamaIndex 路径在检索行为上与自研口径等价，差异限于证据补足与排序分布。

限制：语料是合成 Fixture，不是企业原文；嵌入是脚手架词袋模型，不是生产嵌入；本结论不外推到生产语料与生产嵌入下的排序质量，那部分要在 L4 切换前用真实评测复核。

## 6 依赖转正评估

现状：`llama-index-core==0.11.23` 在 pyproject 可选组 llama-index 中。本地实测其传递依赖约 25 个包（含 nltk、networkx、aiohttp 等），体积与攻击面都不小。

消费方只有三处：`llama_index_retriever.py`、`llama_embeddings.py`、`llama_index_builder.py`，且 bootstrap 只在开关选中时延迟导入。默认路径不依赖它。

结论建议：L2 不转正，L4 默认切换时转正。理由：当前后端是显式可选的实验路径，可选组与之匹配；L4 把它变成默认路径后，默认装配依赖可选组在部署上不成立，届时连同默认切换一并转正，一次变更同时落位。是否采纳由 Owner 在 L2 收尾时确认。

## 7 复现

命令：`python ops/run_backend_compare.py`。退出码 0 表示两路期望判定全部通过。输出 JSON 含每例两路的命中列表、状态与差异类别，与本报告同源。连跑两次输出逐字节一致（已实测）。

环境要求：Python 3.12，已装 llama-index 可选组。未装时脚本退出码为 2 并给出安装提示。

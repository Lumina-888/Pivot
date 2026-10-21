# 检索后端切换说明

本文说明如何在自研检索路径与 LlamaIndex 路径之间切换。切换只影响智能问答的检索环节，文档搜索始终走自研 RetrievalService。对比证据见[双路径行为对比报告](../evidence/llama-index-l2/backend-comparison.md)。

## 1 开关

环境变量是 `PIVOT_RETRIEVAL_BACKEND`。取值只有两个：

- `native`：自研路径，也是默认值。不设置该变量时等同于此取值。
- `llama`：LlamaIndex 路径。问答检索走 LlamaIndexRetriever 与 Qdrant 持久索引。

其他取值在启动校验时报错，服务不会启动。

## 2 前置条件

切到 `llama` 前，五项必须齐备，缺一启动失败：

- 向量存储为 Qdrant，即 `PIVOT_VECTOR_STORE=qdrant`，且集合可达。
- 已安装可选依赖：`pip install -e ./api[llama-index]`。该依赖组包含 `llama-index-core` 与 `llama-index-vector-stores-qdrant`。
- 已设置 `PIVOT_BM25_K1` 与 `PIVOT_BM25_B`。
- 已设置 `PIVOT_QDRANT_VECTOR_SIZE`，与集合维度一致。
- 入库后端为进程内同步，即 `PIVOT_INGEST=sync`。与 celery 组合时启动失败，跨进程索引同步尚未接入。

启动失败时错误信息会指明缺失项。不要在缺项时改默认值绕过校验。

## 3 索引形态与同步

LlamaIndex 路径在同一 Qdrant 集群内使用独立集合，集合名是原生集合名加后缀 `__llama`。两条路径的数据互不覆盖。

启动时分三种情况：

- 集合不存在：按原生集合的载荷全量构建后启动。
- 集合已存在：先校验向量维度与抽样点的 Embedding 模型版本，与当前设置不一致时拒绝启动。校验通过后从集合再水化运行索引。
- 设置 `PIVOT_LLAMA_INDEX_REBUILD=1`：删除既有集合并按原生载荷重建。这是模型版本或维度变更后的重建入口。

运行期同步是对账式的。文档入库完成或被删除后，系统按文档与版本的实时事实，把该文档在 LlamaIndex 集合中的节点对齐到当前版本：旧版本节点删除，当前版本节点重建。同步失败只记录日志，不阻断文档写入；问答每次检索仍有实时授权复核兜底。

## 4 切换步骤

1. 确认前置条件齐备。
2. 设置 `PIVOT_RETRIEVAL_BACKEND=llama`。
3. 重启服务。启动阶段会校验或构建 LlamaIndex 集合，任一原生载荷字段不齐都会启动失败。
4. 用一条已知问题验证问答能返回带引用的答案。
5. 观察一段时间的问答拒答与引用情况，再决定是否长期保留。

从 `llama` 切回 `native` 是同样步骤，把变量改回 `native` 或删除后重启。

## 5 两条路径的差异

- 证据条数：LlamaIndex 路径按融合结果补足到证据上限；自研评测口径下常少于上限。生产装配下两路都会返回足量证据。
- 排序：融合的输入分数分布不同，同一问题的证据顺序可能不同。金标集上两路的标注命中率相同。
- 授权复核：LlamaIndex 路径每次检索都用文档与版本的实时事实复核；自研路径依据载荷中的静态标志。文档删除或版本失效后，LlamaIndex 路径立即不再返回对应证据。
- 状态词：问答层内部状态词不同（ok 与 found），编排器按同一语义处理，对外接口无差别。

## 6 回滚

回滚不需要数据迁移：

1. 设置 `PIVOT_RETRIEVAL_BACKEND=native`，或删除该变量。
2. 重启服务。

原生集合在两条路径下都不被改写。LlamaIndex 集合会保留，回滚后问答立即恢复自研路径行为，之后切回 `llama` 时按第 3 节校验与再水化。如果切到 `llama` 后修改过 BM25 参数，切回时一并核对：自研路径的 BM25 与重排也用同一组参数。

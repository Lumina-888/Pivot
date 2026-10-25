# 检索后端说明

本文说明智能问答的检索后端。自 ADR-020 起问答只走 LlamaIndex。文档搜索始终走自研 RetrievalService。对比证据见[双路径行为对比报告](../evidence/llama-index-l2/backend-comparison.md)。

## 1 后端

问答固定走 LlamaIndex，没有开关。环境变量 `PIVOT_RETRIEVAL_BACKEND` 只认 `llama`。旧 `native` 值在启动校验时报错。问答要求向量存储为 Qdrant，否则装配直接报错。

## 2 前置条件

问答在 Qdrant 部署下要求：

- 向量存储为 Qdrant，即 `PIVOT_VECTOR_STORE=qdrant`，且集合可达。
- 已设置 `PIVOT_BM25_K1` 与 `PIVOT_BM25_B`。
- 已设置 `PIVOT_QDRANT_VECTOR_SIZE`，与集合维度一致。
- worker 进程同步索引时另需 `PIVOT_QDRANT_DISTANCE`。

LlamaIndex 依赖自 L4 起是主依赖，随 api 包一同安装，不再需要可选依赖组。启动失败时错误信息会指明缺失项。不要在缺项时改默认值绕过校验。

## 3 索引形态与同步

LlamaIndex 路径在同一 Qdrant 集群内使用独立集合，集合名是原生集合名加后缀 `__llama`。构建时读原生集合的载荷。两处集合的数据互不覆盖。

启动时分三种情况：

- 集合不存在：按原生集合的载荷全量构建后启动。
- 集合已存在：先校验向量维度与抽样点的 Embedding 模型版本，与当前设置不一致时拒绝启动。校验通过后从集合再水化运行索引。
- 设置 `PIVOT_LLAMA_INDEX_REBUILD=1`：删除既有集合并按原生载荷重建。这是模型版本或维度变更后的重建入口。

运行期同步是对账式的。文档入库完成或被删除后，系统按文档与版本的实时事实，把该文档在 LlamaIndex 集合中的节点对齐到当前版本：旧版本节点删除，当前版本节点重建。同步失败只记录日志，不阻断文档写入；问答每次检索仍有实时授权复核兜底。

同步的执行进程随入库后端而定：

- `PIVOT_INGEST=sync`：API 进程在入库完成后同步，问答立即检索到新文档。
- `PIVOT_INGEST=celery`：worker 进程在入库完成后同步集合；API 进程的运行索引在每次检索前按间隔增量再水化（`PIVOT_LLAMA_REFRESH_SECONDS`，默认 5 秒）。因此 celery 下新入库文档在数秒内即可被问答检索，无须重启 API。删除仍即时生效：删除由 API 进程同步，且授权复核按实时事实拦截；刷新同时把集合侧的删除收敛进运行索引。

## 4 授权复核

LlamaIndex 路径每次检索都用文档与版本的实时事实复核。文档删除或版本失效后，问答立即不再返回对应证据。证据按融合结果补足到证据上限。

# Wave 3 M03 Qdrant VectorStore 客户端限制

环境：`QdrantVectorStore` 默认 CI 用注入的内存 client 子集；Compose Qdrant 为 opt-in（`PIVOT_REQUIRE_COMPOSE=1` 且安装 `api[qdrant]`）。不启动 uvicorn；不把内存 client 标成生产向量索引。

- `PIVOT_VECTOR_STORE=qdrant` 将向量端口接到 `QdrantVectorStore`；endpoint/collection 必须注入，禁止写死生产地址。
- upsert 强制 `version_id + chunk_id` payload；delete 必须带选择器，禁止清空集合。
- 检索/问答仍为 Fake KeywordRetriever；不冻结距离函数、向量维数或检索 k。
- `/readyz` 在仅接通 qdrant 探测时仍因 postgres/minio/redis 失败闭环。
- 无 Redis 客户端，无索引原子发布。

| ID | 状态 | 原因 |
|---|---|---|
| GATE-P0-003 | unverified | 向量客户端不等于状态一致性、幂等、删除与索引原子发布已通过 |

`implemented`（vector store）≠ `verified`。

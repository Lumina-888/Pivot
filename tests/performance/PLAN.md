# 性能与容量方案（Wave 2，未执行）

> `GATE-P0-007` / `NFR-CAP-002` / `NFR-CAP-004` **unverified**。  
> 在线问答 5 并发、目标 100,000 Chunk、P95 延迟均为 **TBD-P0**，本文件不填写默认阈值。

## 计划（Wave 3）

1. 真实检索后端与固定语料代次；
2. 5 并发问答（含 SSE 首 token / 完整答案），记录环境与版本；
3. 100k Chunk 方案：数据生成、索引时间、内存/磁盘峰值、失败注入；
4. 供应商超时与磁盘满；
5. 报告写入 `evidence/`，未通过不得标 verified。

## 本波次

- 进程内 5 并发 `retrieve` 夹具已有（`test_NFR_CAP_002_five_concurrent_retrieves_complete`）；不采集延迟，不标 verified；
- 合成 Chunk 生成器按注入 count 工作；CI 不生成 100k；
- 无真实 ECS 4C8G 压测；无 100k 索引峰值；
- CI 断言本方案存在且声明 unverified；
- 禁止把 Fake 链路耗时写成容量门禁。

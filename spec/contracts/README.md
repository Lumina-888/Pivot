# spec/contracts/ — 机器可读契约（待生成）

**当前状态：占位。** 契约以根目录 `SPEC.md` 为规范源（SPEC §5.1），在 **P0 契约冻结批次**按 TDD 的 Contract 步骤落地（SPEC §0.4），不在本阶段擅自起草未冻结口径。

## 待生成清单

| 文件 | 来源章节 | 覆盖内容 |
|---|---|---|
| `openapi.yaml` | SPEC §5.1~5.5、附录 B | 通用 HTTP 规则、错误包、认证/文档/搜索/会话/Run/导出/后台接口、分页与时间格式 |
| `sse.schema.json` | SPEC §3.3、§5.6 | 事件字段（run_id/message_id/seq/timestamp/stage/payload）、事件类型枚举、终态唯一约束、Last-Event-ID 语义 |
| `worker.schema.json` | SPEC §5.7 | 内部 Worker 契约（status/content/citations/confidence/error_code/trace） |

## 落地约束

- 契约冻结前须完成 API/数据状态契约评审（SPEC §12.3「进入 P1」条件之一）；
- 契约测试与实现同步建立：`tests/contract/` 层防接口漂移（SPEC §10.1、§10.3）；
- 破坏性变更必须升级 `/api/v1` 或提供兼容窗口（SPEC §0.6、附录 B.3）；
- `TBD-P0` 参数（分页方案等）冻结后须回填本目录与测试夹具（SPEC 引言）。

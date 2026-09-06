# spec/scenarios/ — 场景规格（待建立）

**当前状态：占位。** 场景按 SPEC 附录 D 以 Gherkin（`.feature`）逐批建立，第一批在契约冻结后按 E2E 场景落地。

## 待建立文件与来源映射

| 文件 | 来源 |
|---|---|
| `auth.feature` | SPEC §10.5 E2E 场景 1、§4.1 FR-AUTH-*、§12.4 认证域 |
| `ingestion.feature` | SPEC §10.5 E2E 场景 3/4/13、§4.3 FR-DOC-* |
| `retrieval.feature` | SPEC §10.5 E2E 场景 2/5、§4.4 FR-SEARCH-*/FR-RAG-* |
| `qa.feature` | SPEC §10.5 E2E 场景 6/7/8/9/10、§4.5 FR-QA-*、§6 |
| `stream.feature` | SPEC §10.5 E2E 场景 6/7、§4.6 FR-STREAM-*、§5.6 |
| `export.feature` | SPEC §10.5 E2E 场景 11、§4.7 FR-EXPORT-* |

## E2E 基线场景（SPEC §10.5，共 14 条）

1. 用户登录并访问首页；
2. 浏览知识库并筛选；
3. 管理员上传合法 PDF；
4. 文档进入队列并最终 `ready`；
5. 全局搜索并打开正确文档；
6. 创建会话并发送问题；
7. SSE 流式收到阶段、Token、Citation 和终态；
8. 点击引用打开证据抽屉；
9. 无答案问题得到拒答；
10. 从文档详情进入单文档问答且不串库；
11. 导出已完成答案；
12. 管理员查询审计；
13. 删除文档后立即无法检索；
14. 普通用户访问后台和他人会话均被拒绝。

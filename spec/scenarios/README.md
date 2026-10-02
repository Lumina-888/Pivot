# spec/scenarios/ — 场景规格

六组 Gherkin 场景已建立。`qa.feature` 按 SPEC-1.1 / [AGENT_SPEC](../AGENT_SPEC.md) 更新为 LangGraph ReAct；它是 accepted 场景而非已通过的 Agent 测试，执行器/业务实现仍待后续切片。

## 文件与来源映射

| 文件 | 来源 |
|---|---|
| `auth.feature` | SPEC §10.5 E2E 场景 1、§4.1 FR-AUTH-*、§12.4 认证域 |
| `ingestion.feature` | SPEC §10.5 E2E 场景 3/4/13、§4.3 FR-DOC-* |
| `retrieval.feature` | SPEC §10.5 E2E 场景 2/5、§4.4 FR-SEARCH-*/FR-RAG-* |
| `qa.feature` | SPEC §4.5/§7、AGENT_SPEC FR-AGENT-*；工具循环、证据门禁、预算、外发、澄清/恢复、取消 |
| `stream.feature` | SPEC §10.5 E2E 场景 6/7、§4.6 FR-STREAM-*、§5.6 |
| `export.feature` | SPEC §10.5 E2E 场景 11、§4.7 FR-EXPORT-* |

## E2E 基线场景（SPEC §10.5，共 14 条）

1. 用户登录并访问首页；
2. 浏览知识库并筛选；
3. 管理员上传合法 PDF；
4. 文档进入队列并最终 `ready`；
5. 全局搜索并打开正确文档；
6. 创建会话并发送问题；
7. SSE 实时接收脱敏阶段进度，校验并提交后接收正式 Token、Citation 和终态；
8. 点击引用打开证据抽屉；
9. 无答案问题得到拒答；
10. 从文档详情进入单文档问答且不串库；
11. 导出已完成答案；
12. 管理员查询审计；
13. 删除文档后立即无法检索；
14. 普通用户访问后台和他人会话均被拒绝。

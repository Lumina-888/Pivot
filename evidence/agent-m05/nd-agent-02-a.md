# ND-AGENT-02-A 内部 Contract 提案证据

- **日期 / 基线**：2026-10-02；`E:/AI Project/Pivot`、main `cdadc53`。
- **Accountable / 范围**：M05 内部模型/工具/State/EvidenceRegistry 提案；M00 治理与进度同步。提案 [AGENT-INTERNAL-0.1-draft.1](../../progress/changes/20261002-M05-agent-internal-contract.md)。
- **结论**：02-A 为 review（proposed 待消费者/Owner 签认），不是 done/发布；02 父票与业务实现保持 blocked。DR-010/011、依赖锁定、恢复公开 Contract 和所有 GATE 未关闭。

## 交付

- 明确原生 AIMessage.tool_calls → 同 ID ToolMessage → 再决策的串行协议，严格两个只读工具参数与无工具控制意图。
- 定义可信 RunContext 与可序列化敏感 AgentState、EvidenceRegistry 去重/来源/版本/真实定位、Finalizer 仅 Claims/evidence_ids 和内部失败分类。
- 4 份内嵌 JSON Schema 只作拟议机器形状；11 组运行时 Fake/Red 用例设计及 7 个消费者 pending 签认项。
- 记录旧 QA/装配端口丢检索元数据的差距，留给批准后的 02-D，不本轮修改业务端口。
- 未修改公共 schema、路由、状态/错误枚举、SPEC 语义、依赖或迁移；没有 Agent 生产预算默认值。

## 验证命令与结果

环境：Windows PowerShell 5.1；Python 3.12.10、pytest 9.1.1、jsonschema 4.26.0、PyYAML 6.0.3、ruff 0.16.6（仓库 `.venv`）。

| 命令 | 结果 / 能证明什么 |
|---|---|
| `& .pi/artifacts/nd-agent-02-a/check-proposal.ps1` | 4 schema 可解析并满足 Draft 2020-12；10 个合法形状接受、28 个非法形状拒绝；无 default 字段。仅提案 artifact 检查 |
| `.venv/Scripts/python -B -m pytest tests/contract --ignore=tests/contract/stream -q -p no:cacheprovider` | 48 passed；既有发布契约回归 |
| `.venv/Scripts/python -B -m pytest tests/unit/qa tests/unit/runs tests/contract/stream -q -p no:cacheprovider` | 79 passed；既有答案安全/Run/SSE 回归，不是新 Agent 用例 |

提案检查脚本留在仓库 `.pi/artifacts/nd-agent-02-a/`，不入库、不写 C 盘。首两次检查脚本因 PowerShell 管道 BOM 与 native `-c` 引号传递失败，改为 utf-8-sig 解码与 Base64 传递检查代码后通过；不是运行时业务 Red/Green。

同一检查脚本收尾验证 **10 个 Markdown / 60 条本地链接 / 29 个工单（4 ready、1 review、24 blocked）通过**；`git diff --check` 通过，仅保留既有 LF/CRLF 转换提示。未新增业务测试，提案 §8 的计划测试均未实施。

主动 `lens_diagnostics(source=lsp, scope=paths)` 检查 10 个修改文档：全部 unavailable（marksman/typos client 未 ready）；0 diagnostics 不代表 clean。文档静态/形状检查与既有回归不代替消费者语义签认，LSP 限制已记录。

## 限制与工作区

- 未运行真实 StateGraph、消息往返、授权/外发执行、预算、checkpoint 或 live 供应商测试；schema 接受形状不证明 evidence_id 归属、支持性或工具协议语义。
- 未跑全量分组/Web/Compose/ECS；本轮没有这些路径的变更。
- 开场已有 6 个业务源码修改与用户未跟踪文件，全部保留且未纳入本提交。79 项回归基于当前组合工作区，不作为已有改动的独立验收。
- 消费者 M00/M01/M03/M04/M05/M06/M11 均 pending；编写提案不等于批准，不能发布 spec/contracts 新内部版本。
- 下一刀 02-B/DR-010 提案与明确注入的受控 Fixture 设计，然后 02-C 依赖验证/申请；数值、锁版本和运行策略必须另行获批。

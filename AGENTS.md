# 问枢 Pivot 协作指令

本文件是所有开发会话进入仓库后的第一份执行指令。项目需求以 [`SPEC.md`](SPEC.md)（SPEC-1.1）为规范源，Agent 细则以其引用的 [`AGENT_SPEC.md`](spec/AGENT_SPEC.md) 为准；模块边界、文件所有权和 Git 协议以 [`MODULE_SPEC.md`](MODULE_SPEC.md)（1.2 主线开发）为准；当前进度以 [`PROGRESS.md`](PROGRESS.md) 与 `progress/modules/` 为准。

当前目标是 **LangGraph StateGraph + 原生工具调用型受控 ReAct Agent**。旧线性 RAG、LangGraph 暂缓申请和历史技术方案不是当前架构依据；真实 Agent 尚未实现；ND-AGENT-01 答案安全迁移基线已修复，默认下一刀为 ND-AGENT-02 的内部 Contract 前置（预算/锁依赖未满足时业务实现 blocked）。

## 开始任何工作前

1. 确认工作区是仓库根 `Pivot/`，分支是 `main`。当前 Linux 路径为 `/home/lumina888/Projects/Pivot`；`E:/AI Project/Pivot` 是历史 Windows 路径。不要进入或新建 `../Pivot-Mxx-*` worktree。
2. 读取 `SPEC.md`、`spec/AGENT_SPEC.md`、`MODULE_SPEC.md`、`PROGRESS.md`；
3. 确认本切片范围，以及涉及模块的 `progress/modules/Mxx.md`；
4. 若 DoR 不满足，先写进度/变更申请，不要直接写业务代码。

## 开发纪律

- 遵循 SPEC §0.4：Red → Contract → Green → Refactor → Integration → Regression；测试命名为 `test_<requirement_id>_<behavior>()`。
- 需求、状态机、错误码、API/SSE/Worker 字段以 `SPEC.md` 为准；不得私自改变 `TBD-P0`。
- Agent 改造遵循 ADR-009：先修答案门禁，再真实 LangGraph 工具循环；未冻结预算/恢复/checkpoint Contract 的相关切片不得直接实现。
- 不把 `.pi/` 讨论稿、旧绿灯或依赖安装当新 Agent 验收；不得静默 fallback 到线性 RAG。
- 每个文件仍有 Accountable Owner（见 MODULE_SPEC）。主线切片可以一次改多个模块路径，但必须在进度里写明。
- 公共契约、迁移、共享错误码的变更走 `progress/changes/`。
- 外部 LLM/Embedding/Rerank 和基础设施测试使用 Fake/Stub 或受控 Fixture；不得提交真实密钥、企业文档或供应商 URL。
- 不得为了修绿而绕过授权、过滤、幂等、审计或测试。
- 影响状态机、权限、引用/删除语义、模型或检索配置时，必须登记 ADR（SPEC §0.6、附录 E）。

## 会话交接与收尾

切片结束前必须：

1. 运行受影响测试和静态检查，记录命令、版本、结果与限制；
2. 更新相关 `progress/modules/Mxx.md` 和根 `PROGRESS.md`；
3. 提交格式 `type(Mxx): 中文说明 [需求或测试 ID]`；跨模块时在正文列出路径；
4. 测试通过后可创建切片/模块 tag；
5. 写明未完成项、TBD-P0 和下一步。

## 常用命令

```bash
cd /home/lumina888/Projects/Pivot
source .venv/bin/activate
git status --short
git log --oneline --decorate -20

python ops/run_grouped_tests.py --skip-web
ruff check --config api/pyproject.toml api/src worker/src

npm --prefix web test
npm --prefix web run typecheck
npm --prefix web run lint
```

不要执行 `git worktree add "../Pivot-Mxx-*"`。历史 worktree 由 Owner 手动删除。

## 恢复开发提示

本机开发/测试环境见 [`ops/runbook-local-linux.md`](ops/runbook-local-linux.md)：Python 3.12.10 与已有回归/浏览器测试可用，Docker 真实存储联调仍待代理授权；不得把本机配置当成 02-C 目标平台锁验证或 Agent 签认。

新会话说明“继续主线”或点名下一刀（例如 ND-AGENT-02 Contract 前置）即可。先读 [`HANDOFF.md`](HANDOFF.md) 了解 2026-10-02 ReAct 规格迁移与当前实现差距；2026-09 的 Wave 3 历史证据仍保留。不要依赖上一会话的聊天记录；聊天记录不是项目事实，版本化进度文件、commit、tag 和测试证据才是交接依据。

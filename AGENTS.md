# 问枢 Pivot 协作指令

本文件是开发会话进入仓库后的第一份执行指令。

需求以 [SPEC.md](SPEC.md) 的 SPEC-1.1 为准。Agent 细则以 [AGENT_SPEC.md](spec/AGENT_SPEC.md) 为准。模块边界、文件所有权和 Git 协议以 [MODULE_SPEC.md](MODULE_SPEC.md) 的 1.2 主线为准。当前进度以 [PROGRESS.md](PROGRESS.md) 和 `progress/modules/` 为准。

当前目标是 LangGraph StateGraph，以及原生工具调用型受控 ReAct Agent。旧线性 RAG、LangGraph 暂缓申请和历史技术方案，都不是当前架构依据。

基线是 `17ac93a`。下列契约已经发布：

- 02-A、02-B 和 02-C 的内部契约
- 03-A 的恢复契约 contract-v0.2
- 04-A 的持久化契约

02-D 至 02-H，以及 03-B、03-C、03-D 和 03-E，已有开发实现。04-B 的结果提交和 04-C 的 checkpoint 框架已经提交。跨进程恢复尚未完成。

默认下一刀是 04-C 的后续，以及 04-D 至 04-F。DR-010 的生产数值尚未关闭。开发实现不等于运行批准，也不等于 GATE 通过。

## 开始工作前

1. 确认工作区是仓库根 `Pivot/`，分支是 `main`。当前 Linux 路径是 `/home/lumina888/Projects/Pivot`。`E:/AI Project/Pivot` 是历史 Windows 路径。不要进入或新建 `../Pivot-Mxx-*` worktree。
2. 读取 `SPEC.md`、`spec/AGENT_SPEC.md`、`MODULE_SPEC.md` 和 `PROGRESS.md`。
3. 确认本切片范围，以及涉及模块的 `progress/modules/Mxx.md`。
4. DoR 不满足时，先写进度或变更申请，再写业务代码。

## 开发纪律

- 遵循 SPEC 第 0.4 节。顺序是 Red、Contract、Green、Refactor、Integration 和 Regression。测试命名为 `test_<requirement_id>_<behavior>()`。
- 需求、状态机、错误码，以及 API、SSE 和 Worker 字段，以 `SPEC.md` 为准。不得私自改变 `TBD-P0`。
- Agent 改造遵循 ADR-009。先修答案门禁，再接入真实 LangGraph 工具循环。02、03-A 和 04-A 的契约已经发布。DR-010 的生产数值和 04 的跨进程恢复完成之前，开发实现不能标成运行批准。
- `.pi/` 讨论稿、旧测试绿灯和依赖安装，都不能当作新 Agent 验收。不得静默回退到线性 RAG。
- 每个文件仍有 Accountable Owner，见 MODULE_SPEC。主线切片可以一次修改多个模块路径，但必须在进度里写明。
- 公共契约、迁移和共享错误码的变更，走 `progress/changes/`。
- 外部 LLM、Embedding、Rerank 和基础设施测试，使用 Fake、Stub 或受控 Fixture。不得提交真实密钥、企业文档或供应商 URL。
- 不得为了修绿而绕过授权、过滤、幂等、审计或测试。
- 状态机、权限、引用、删除语义、模型或检索配置发生变化时，必须登记 ADR。依据是 SPEC 第 0.6 节和附录 E。

## 会话交接与收尾

切片结束前完成下面五项：

1. 运行受影响测试和静态检查。记录命令、版本、结果和限制。
2. 更新相关 `progress/modules/Mxx.md` 和根目录 `PROGRESS.md`。
3. 提交说明使用 `type(Mxx): 中文说明 [需求或测试 ID]`。跨模块时在正文列出路径。
4. 测试通过后，可以创建切片或模块 tag。
5. 写明未完成项、`TBD-P0` 和下一步。

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

## 恢复开发

本机环境见 [Linux runbook](ops/runbook-local-linux.md)。Python 3.12.10，以及已有回归和浏览器测试，可以运行。Docker 真实存储联调仍等待代理授权。

02-C 已有 Windows 候选、Linux 候选，以及 Ubuntu Hosted CI 的技术验证。正式角色锁、供应链和安全签认尚未完成。Arch 宿主和候选锁不能当作发布依赖。

新会话可以说明“继续主线”，或点名下一刀，例如 04-C 后续。先读 [HANDOFF.md](HANDOFF.md) 的当前入口。该文件第 4 节之后是历史轮次，不是待办。2026-09 的 Wave 3 证据仍然保留。

聊天记录不是项目事实。版本化进度文件、commit、tag 和测试证据，才是交接依据。

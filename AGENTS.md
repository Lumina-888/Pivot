# 问枢 Pivot 协作指令

本文件是所有开发会话进入仓库后的第一份执行指令。项目需求以 [`SPEC.md`](SPEC.md) 为规范源；并行模块边界、文件所有权和 Git 协议以 [`MODULE_SPEC.md`](MODULE_SPEC.md) 为准；当前进度以 [`PROGRESS.md`](PROGRESS.md) 与 `progress/modules/` 为准。

## 开始任何工作前

1. 读取 `SPEC.md`、`MODULE_SPEC.md`、`PROGRESS.md`；
2. 确认自己负责的模块 `Mxx`、分支、worktree 和当前波次 tag；
3. 读取 `progress/modules/Mxx.md`，核对 DoR、允许/禁止修改路径、依赖契约版本和未决变更；
4. 若 DoR 不满足，先写进度/变更申请，不要直接写业务代码。

## 开发纪律

- 遵循 SPEC §0.4：Red → Contract → Green → Refactor → Integration → Regression；测试命名为 `test_<requirement_id>_<behavior>()`。
- 需求、状态机、错误码、API/SSE/Worker 字段以 `SPEC.md` 为准；不得私自改变 `TBD-P0`。
- 每个文件只有一个 Owner。只修改 `MODULE_SPEC.md` 所列的本模块路径；公共文件变更走 `progress/changes/`。
- 外部 LLM/Embedding/Rerank 和基础设施测试使用 Fake/Stub 或受控 Fixture；不得提交真实密钥、企业文档或供应商 URL。
- 不在集成分支绕过授权、过滤、幂等、审计或测试来“修绿”；业务缺陷退回 Accountable 模块。
- 影响状态机、权限、引用/删除语义、模型或检索配置时，必须登记 ADR（SPEC §0.6、附录 E）。

## 会话交接与收尾

模块会话结束前必须：

1. 运行模块测试和静态检查，记录命令、版本、结果与限制；
2. 更新 `progress/modules/Mxx.md`，写明完成项、未完成项、需求/测试/证据、TBD-P0、变更申请和下一步；
3. 只提交所有权范围内的文件；使用 `type(Mxx): 中文说明 [需求或测试 ID]`；
4. 创建模块完成 tag（仅在测试通过后）；
5. 将 commit/tag 和合并前置条件交给集成会话；
6. 不直接并发修改根 `PROGRESS.md`，由集成会话汇总。

集成会话完成后更新根 `PROGRESS.md` 和 `spec/acceptance/matrix.md`，并创建波次 tag。

## 常用命令

```bash
# 查看当前隔离状态
git status --short
git worktree list

# 创建模块 worktree（先确保基线已提交）
git worktree add "../Pivot-M04-retrieval" module/M04-retrieval

# Python 测试（实际入口以模块 pyproject 为准）
python -m pytest tests/unit -q
ruff check api tests

# 前端检查（进入 web/ 后执行）
npm ci
npm run lint
npm run test
```

## 恢复开发提示

新会话只需说明“继续开发 Mxx”或“执行下一波集成”，然后按本文开头顺序读取文件。不要依赖上一会话的聊天记录；聊天记录不是项目事实，版本化进度文件、commit、tag 和测试证据才是交接依据。

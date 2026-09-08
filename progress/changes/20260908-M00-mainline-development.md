# 变更申请：废止默认并行 worktree，改为主线开发

- **日期**：2026-09-08
- **申请人**：仓库 Owner（API 配额不足以支撑多会话并行）
- **背景**：MODULE-SPEC-1.0 默认 5–6 个会话、每个模块独立 worktree。当前 API 限制无法并行；磁盘上已堆积约 20 个历史 worktree，容易改错目录。
- **原契约/现状**：`MODULE_SPEC.md` 1.0 要求 `git worktree add "../Pivot-Mxx-*"`；`AGENTS.md` / `PROGRESS.md` / `README.md` 把 worktree 当作开场硬条件。
- **拟变更内容**：
  - 升级 `MODULE_SPEC.md` 为 1.1：**默认主线开发**。工作区仅为 `E:/AI Project/Pivot`，分支默认 `main`。
  - 一次会话可做一条垂直切片，允许改多个模块路径；Accountable 映射仍保留，不再为每个模块新建 worktree。
  - 不再要求独立集成会话才能改 `PROGRESS.md`。
  - 历史 `Pivot-Mxx-*` 为遗留副本，禁止在其中继续开发；由 Owner 手动删除，本变更不批量删目录。
  - SDD/TDD、TBD-P0、契约优先级、禁止提交密钥等纪律不变。
- **影响模块**：M00（治理文档）；全部模块的 Git 工作方式。不改业务代码。
- **兼容方案**：已合入 `main` 的模块 tag 与波次 tag 保留。旧 `module/Mxx-*` 分支视为只读历史。
- **测试 ID**：无代码测试；以文档一致性为准。
- **是否触发 ADR**：否（协作流程，不改状态机/权限/检索语义）。
- **审核结果**：2026-09-08 Owner **批准**。

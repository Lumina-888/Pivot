# SPEC-1.1 按当前进度拆分剩余 Tickets

- **日期 / 状态**：2026-10-02 / accepted（本次用户请求的文档拆票范围；不是新 Contract/ADR 审批）。
- **Accountable**：M00；规范来源 M05/M01/M03/M06/M11 等模块责任不变。
- **原契约 / 实现基线**：SPEC-1.1、AGENT-SPEC-1.0、ADR-009；发布 contract-v0.1；main `8cd4727`（ND-AGENT-01）。
- **触发**：用户要求依据现在开发进度将 SPEC 转为 tickets。

## 背景

旧工单已区分 Agent/Wave 3/P0/P1/STG，但 ND-AGENT-02~05 合并了 Contract、实现和受控环境验收；父票 blocked 时缺少明确下一张前置票。后台 metrics/tasks、运行时持久审计、首次改密跨实例与签名 URL 消费者验收也缺少独立追踪。

ND-AGENT-01 已完成答案安全子集；没有真实 LangGraph 循环/checkpoint，全部 GATE-P0 仍 unverified。工作区已有业务源码修改与用户未跟踪文件不属于本次文档整理，不将它们作为新通过证据。

## 文档变更

1. 新增 [剩余 Tickets](../tickets/spec-1.1-remaining.md)：29 张细化票，每票唯一 Accountable、来源、状态/依赖、场景/异常、范围/数据、路径/交付、计划测试、DoD 与不做项；含全 SPEC 范围/门禁/参数包映射。
2. 保留既有父票、需求 ID、历史完成记录；ND-AGENT-02~05 仍 blocked。5 张 ready 仅开放 Contract 调研/提案和 Red 设计，不授权业务实现。
3. 默认下一刀细化为 ND-AGENT-02-A，随后 02-B/02-C；03-A/04-A 可提前 proposed 设计，但发布与实现仍按依赖受阻。
4. 补 ND-GAP-01~04，ND-P0-01-A 业务复核及 ND-STG-04-A apply。对尚未验证的密码/下载机制先确认差距，不能据进度直接断言漏洞或私增字段/路由。
5. 明确 ND-P0-03/05 原 ready 为准备口径；live 执行/业务签认未确认则 blocked。低敏 staging 历史延期范围不变，企业文档审批仍阻断正式门禁。
6. 同步工单入口、NEXT-DEV-1.18、验收矩阵的执行清单引用、根 PROGRESS 与 M00 进度。

## 影响与兼容

实际修改仅 `progress/tickets.md`、`progress/tickets/spec-1.1-remaining.md`、`progress/next-dev-spec.md`、本文件、`progress/modules/M00.md`、`PROGRESS.md`、`spec/acceptance/matrix.md`。不修改业务源码、SPEC/AGENT_SPEC 语义、公开 API/SSE/Worker schema、依赖或迁移。

不新增 ADR 决策，不冻结 TBD-P0；预算/恢复/checkpoint 等真正 Contract 在相应前置子票另行提案和审核。规格的唯一 Accountable 与主线串行协议不变，不授权委派或 worktree。

## 验证

- 逐票标题与索引一致、29 个唯一子票 ID、5 个 ready 均仅前置范围；SPEC/FR-AGENT 覆盖与全部 P0 门禁有对应票。
- 本地 Markdown 链接/票号/前置范围检查；`git diff --check`。
- 公共契约回归分组执行：`.venv/Scripts/python -B -m pytest tests/contract --ignore=tests/contract/stream -q -p no:cacheprovider`。
- 实际命令/版本/结果及限制记录在 PROGRESS/M00 本轮日志；新测试名称只为计划，不能当通过证据。未重跑业务全量/Web/live/Compose，新拆票不改变验收状态。

## 审核边界与下一步

本次按 Owner 请求接受拆票文档，不代替各模块对内部接口/依赖/迁移/公开恢复协议的后续审批。下一张 ND-AGENT-02-A 只做内部模型/工具/State Contract 提案，DR-010、锁依赖与 DR-011 仍开放。

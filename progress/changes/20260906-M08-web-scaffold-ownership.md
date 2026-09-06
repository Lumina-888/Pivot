# 变更申请：Wave 0 Web 工程骨架与共享工具所有权澄清

- **日期**：2026-09-06
- **申请人**：M08 Web 基础与设计系统会话
- **背景**：M08 需要可构建的 Next.js App Router 工程、锁文件和共享 className 工具，才能冻结设计令牌与 API/SSE client。`MODULE_SPEC §3 M08 允许修改` 列出了 `web/package.json`、`web/next.config.*`、`web/tsconfig.json`、`web/app/globals.css`、组件与 `web/lib/{api,auth,stream}`，但未显式列出锁文件、ESLint、根 layout/page 和 `web/lib/cn.ts`。同时规定“页面 routes 不在 M08 所有权内”。
- **原契约/现状**：`web/` 在 Wave 0 前不存在；M09 拥有 `web/app/(user)/**`（含首页 `/`），M10 拥有 `web/app/(admin)/**`。
- **拟变更内容**：
  - Wave 0 期间，M08 可创建并维护以下工程骨架，不实现产品页面业务：
    - `web/package-lock.json`、`web/.eslintrc.json`、`web/next-env.d.ts`
    - `web/app/layout.tsx`（根布局，共享 Toaster/元数据）
    - `web/app/page.tsx`（临时装配页，明确声明非首页业务实现）
    - `web/lib/cn.ts`（共享组件 className 辅助）
  - M09 实现员工前台 `/` 时必须替换或删除 `web/app/page.tsx`，避免与 `web/app/(user)/page.tsx` 路由冲突。
  - 不引入 shadcn/ui 默认主题；S3 视觉基线以 CSS 变量实现。后续若引入 shadcn 原语，须再申请并通知 M09/M10。
- **影响模块**：M08（写入）；M09/M10（消费共享布局/组件，并接管产品路由）。
- **兼容方案**：骨架页不含登录/知识库/对话/后台业务；浏览器只走 `/api/v1` 与 SSE，不直连模型、向量库或 MinIO。
- **测试 ID**：`test_NFR_UX_design_tokens_align_s3`、`test_NFR_UX_001_keyboard_and_focus_visible`、`test_NFR_UX_003_aria_live_and_reduced_motion`、`test_FR_AUTH_001_*`、`test_FR_STREAM_002_*`、`test_FR_STREAM_003_*`。
- **是否触发 ADR**：否（不改变状态机、权限、引用/删除语义、模型或检索配置）。
- **审核结果**：待 M00/集成维护者在 Wave 0 退出评审中确认。

# language: zh-CN
@qa @e2e
功能: 问答、引用、拒答与可信度
  来源：SPEC §4.5（FR-QA-001~006）、§6.4~6.5、§7、§10.5 E2E 6/8/9/10、§12.4 问答域

  背景:
    假设 已登录用户且存在可提问的授权会话

  @FR-QA-001 @E2E-6
  场景: 沿受控主图完成一次问答
    当 用户发送问题
    那么 按 normalize → classify → retrieve → rerank → build_evidence → draft_answer → verify_claims → finalize/refuse 执行
    并且 检索节点不生成最终结论；写作节点不改变权限范围（FR-QA-001）

  @FR-QA-002 @FR-QA-005 @E2E-6 @E2E-8
  场景: 结构化 Claim/Citation 与证据抽屉
    当 回答生成完成
    那么 答案先保存结构化 Claims 与 Citation 再渲染 Markdown（FR-QA-002）
    并且 每个事实性 Claim 有候选证据 ID；候选集合外的 Citation 直接判错
    当 用户点击引用
    那么 打开证据抽屉展示允许展示的证据原文与定位（locator），并提示定位限制（§6.4）
    并且 普通用户仅看到路由/检索/重排/合成/校验等阶段摘要，不暴露思考链/系统 Prompt/敏感上下文（FR-QA-005）

  @FR-QA-003 @E2E-9
  场景: 无依据问题拒答
    当 无命中、低相关性、权限过滤后无证据、冲突未解决或外发不允许
    那么 Run 进入 uncertain/refused，不输出无引用事实答案，不以常识补全企业事实（FR-QA-003、§6.5）

  @FR-QA-004
  场景: Citation Verifier 失败安全降级
    当 Verifier/judge 超时、不可用或返回非法结构
    那么 不默认为通过；可删除无依据句、标记存疑或拒答（VERIFICATION_UNAVAILABLE）

  @FR-QA-006
  场景: 澄清有界且上下文隔离
    当 用户问题需澄清且本 Run 尚未澄清
    那么 进入 waiting_for_user 并持久化；恢复（resuming）后可继续检索
    当 同一 Run 第二次需要澄清
    那么 不再发起第二轮澄清（每 Run 最多 1 轮，SPEC §7.3）
    并且 Worker 不保存跨任务记忆；不同用户会话绝不共享上下文

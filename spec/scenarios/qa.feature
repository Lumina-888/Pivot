# language: zh-CN
@qa @e2e
功能: LangGraph 受控 ReAct 问答、引用与可信度
  来源：SPEC-1.1 §4.5/§7，AGENT-SPEC-1.0 §2~11，ADR-009
  本文件是 accepted 场景规格，尚不代表新 Agent 已实现或场景已有执行器

  背景:
    假设 已登录用户且存在可提问的授权会话
    并且 模型与工具使用可控 Fake 且图使用真实 LangGraph StateGraph

  @FR-QA-001 @FR-AGENT-001 @E2E-6
  场景: 工具观察驱动 Agent 再决策
    假设 首次合法检索证据不足且仍有剩余预算
    当 Agent 通过原生 tool_calls 调用 search_knowledge 并收到对应 ToolMessage
    那么 模型根据 Observation 选择新的合法行动而不是固定线性流水线
    并且 可以改写查询再次搜索或读取已登记证据
    并且 准备回答时必须进入结构化 Finalizer 和 Verifier

  @FR-AGENT-001 @FR-AGENT-010
  场景: 不同观察产生不同工具路径
    当 同一 Agent 分别收到充分与不足的检索观察
    那么 scripted Fake 模型可以选择不同的后续工具序列
    并且 业务路由不硬编码总是检索两次

  @FR-AGENT-002 @FR-AGENT-003 @FR-RAG-003
  场景: 工具不能扩大 scope 或伪造身份
    假设 当前 Run 的服务端 scope 为 document 且指向 doc_A
    当 模型提交未知工具、额外 principal 或 scope 参数或者其他 Run 的 evidence_id
    那么 工具守卫拒绝该行动且不返回受保护正文或泄露存在性
    并且 工具执行只使用服务端可信上下文

  @FR-AGENT-003 @FR-QA-005
  场景: 文档注入和外发限制不能绕过
    假设 工具观察包含要求忽略权限的文档文本或禁止外发的数据
    当 Agent 准备调用 Planner Finalizer Verifier 或备用外部模型
    那么 文档指令不能改变白名单和权限
    并且 受限正文 摘要 历史观察和敏感元数据不得外发

  @FR-QA-002 @FR-AGENT-005 @E2E-8
  场景: 仅从支持校验通过的事实渲染答案
    当 模型提出事实性 Claims 与本 Run evidence_ids
    那么 服务端校验引用存在性 绑定 候选归属 权限 版本及文本支持关系
    并且 最终 Markdown 仅由全部通过校验的事实渲染
    并且 Claims Citation 最终 Message 和终态提交后才公开答案
    当 用户点击引用
    那么 证据抽屉显示真实且允许展示的定位和证据

  @FR-QA-002 @FR-QA-004 @FR-AGENT-005
  场景: 自由 Markdown 不能由另一组证据 Claims 背书
    假设 证据仅描述迟到规则
    当 模型输出每人获得百万美元奖金的自由 Markdown
    那么 不得从证据另造 Claims 后保留该 Markdown 并标记 answered
    并且 候选外或悬空 Citation 不能因其他有效引用而被忽略后放行全文

  @FR-QA-003 @FR-AGENT-004 @E2E-9
  场景: 无证据且无合法补证机会时安全结束
    假设 多轮合法检索仍无证据且预算耗尽或不存在合法补证路径
    当 Agent 尝试准备最终答案
    那么 返回 refused 或 uncertain 而不以常识补全企业事实
    并且 权限或外发禁止不能通过换工具或供应商重试绕过

  @FR-QA-004 @FR-AGENT-005
  场景: Verifier 故障不能默认为通过
    当 Verifier 或 judge 超时 不可用或返回非法结构
    那么 不得 answered
    并且 只有存在合法补证路径且有预算时才继续否则存疑或拒答

  @FR-QA-006 @FR-AGENT-007
  场景: 一轮澄清经授权恢复同一 Run
    假设 本 Run 尚未澄清且恢复公开契约已冻结
    当 Agent 需要用户补充信息
    那么 通过 interrupt 持久化并进入 waiting_for_user
    当 会话 owner 按已冻结契约提交回复
    那么 用 Command resume 恢复同一 Run 并重新授权
    并且 澄清次数和已消费预算不重置且最多一轮澄清
    并且 不同用户或 Run 不共享内部上下文

  @FR-AGENT-004 @FR-AGENT-006
  场景: checkpoint 恢复保留预算且只有一个有效执行者
    假设 工具节点已完成 checkpoint 后执行进程异常退出
    当 两个执行者竞争恢复该 Run
    那么 数据库认领和 fencing 只允许一个有效执行者继续
    并且 从合法 checkpoint 继续且不重置预算或重复发布结果
    并且 外部供应商调用计费重放风险有记录而非宣称 exactly-once

  @FR-AGENT-008 @FR-STREAM-003 @FR-STREAM-004
  场景: 取消和 SSE 重连不重新执行 Agent
    当 用户取消非终态 Run 后模型返回结果
    那么 晚到答案不能覆盖 cancelled
    当 用户使用 Last-Event-ID 重连
    那么 只重放已提交事件且不触发新的 Agent 执行
    并且 seq 单调且终态唯一

  @FR-QA-005 @FR-AGENT-008
  场景: 公开轨迹不泄漏内部消息或未验证事实
    当 LangGraph 产生工具消息 模型草稿或内部执行事件
    那么 SSE 只投影白名单脱敏行动摘要
    并且 不包含思考链 系统 Prompt 工具原始参数或受保护 Observation
    并且 最终 token citation completed 只在校验及持久化后发送

  @FR-AGENT-009
  场景: 新 Agent 模式不得静默回落旧线性实现
    当 框架依赖 模型工具能力或必需预算配置缺失
    那么 启动或请求失败闭环而不是使用旧线性 RAG 冒充 ReAct

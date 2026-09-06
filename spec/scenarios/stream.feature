# language: zh-CN
@stream @e2e
功能: Run 状态、SSE 事件流与恢复
  来源：SPEC §4.6（FR-STREAM-001~005）、§3.2 Run 状态机、§3.3 SSE 事件规则、§5.6、§10.5 E2E 6/7、§12.4 SSE 域
  说明：SSE data 负载须通过 spec/contracts/sse.schema.json；事件名见 x-event-types；序列约束（seq 严格递增、终态唯一且为末条）由契约序列测试保证。

  背景:
    假设 已登录用户且已有授权会话

  @FR-STREAM-001 @E2E-6
  场景: Run 幂等创建
    当 用户以相同 conversation_id、question 与 idempotency_key 重复提交 POST /runs
    那么 返回同一 Run（run_id/message_id），不重复创建 Message、不重复计费
    当 相同 idempotency_key 但参数不同再次提交
    那么 返回 IDEMPOTENCY_CONFLICT

  @FR-STREAM-002 @E2E-7
  场景: SSE 有序事件流至终态
    当 用户订阅 /runs/{id}/events
    那么 依次收到 run_started、stage、token、citation（如适用）事件直至唯一终态事件
    并且 每个事件携带 run_id/message_id/seq/timestamp/stage/payload；seq 单调递增
    并且 终态事件（completed/uncertain/refused/failed/cancelled）最多一个且为该 Run 最后一条
    并且 前端不因事件重放渲染重复答案（FR-STREAM-002）

  @FR-STREAM-003 @E2E-7
  场景: 断线重连按 Last-Event-ID 补发
    假设 客户端已接收 seq ≤ n 的事件后连接中断
    当 客户端以 Last-Event-ID=n 重连
    那么 服务端仅补发 seq > n 的事件且无重复；终态仍保持唯一
    当 补发不可用
    那么 客户端查询 GET /runs/{id} 读取持久化终态（SSE 非唯一事实来源，§3.3、附录 B.3）

  @FR-STREAM-004
  场景: 取消运行幂等且尽量向链路传递
    当 Run 所有者（或有权限管理员）取消未完成 Run
    那么 返回终态 cancelled；取消请求尽量传递到 LLM、检索与 Worker
    当 取消请求重复提交或 Run 已完成
    那么 取消幂等生效；已完成 Run 状态不被改写

  @FR-STREAM-005
  场景: 重试预算与不可重试错误
    当 供应商超时/429/临时 5xx/临时网络错误发生
    那么 按预算重试（指数退避，预算 TBD-P0）；query rewrite 最多 2 次
    当 权限、格式、无证据、禁止外发错误发生
    那么 不重试，Run 进入明确终态并记录 error_code（附录 B.1 retryable=false）

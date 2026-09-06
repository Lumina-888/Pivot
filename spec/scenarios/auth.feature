# language: zh-CN
@auth @e2e
功能: 认证与资源授权
  来源：SPEC §4.1（FR-AUTH-001~004）、§4.2（FR-RBAC-001~004）、§3.4、§10.5 E2E 1/14、§12.4 认证/RBAC 域
  说明：所有断言均以服务端行为为准；前端隐藏入口不能替代服务端授权（SPEC §1.2、§8.1）。

  背景:
    假设 系统已部署且 /api/v1 可用

  @FR-AUTH-001 @E2E-1
  场景: 有效用户登录并访问首页
    当 用户以正确密码提交登录
    那么 登录成功并返回短时 access token
    并且 refresh token 仅经 HttpOnly/Secure/SameSite Cookie 下发
    并且 前端 localStorage 不存在长期凭证（NFR-SEC-005、FR-AUTH-001）
    当 携带 access token 请求首页所需受保护接口
    那么 请求被允许并返回授权范围内容

  @FR-AUTH-002
  场景: 登录失败统一响应并触发限流
    当 用户不存在或密码错误提交登录
    那么 返回统一错误（AUTH_INVALID_CREDENTIALS），不泄露"用户不存在/密码错误"差异
    并且 失败登录被记录为审计事件
    当 连续失败达到冻结阈值（阈值 TBD-P0）
    那么 登录被限流，超限窗口内拒绝（数值冻结前不承诺具体值）

  @FR-AUTH-003 @E2E-1
  场景: 刷新、退出与停用立即失效
    当 有效用户请求刷新
    那么 返回新的短时 access token
    当 用户退出
    那么 refresh token 不再可用且 Cookie 被清除
    假设 管理员停用该用户（§3.4）
    那么 其既有 Token 立即失效，无法访问受保护资源，且停用被审计

  @FR-AUTH-004
  场景: 密码生命周期
    假设 管理员创建用户（含初始密码）
    那么 初始密码不经过普通日志或 URL 传输（传递机制 TBD-P0）
    当 用户首次登录后修改密码
    那么 修改成功且后续使用新密码
    当 用户忘记密码且管理员重置
    那么 重置凭证仅经安全通道返回

  @FR-RBAC-001 @E2E-14
  场景: 普通用户访问后台被服务端拒绝
    当 普通用户携带有效 Token 请求 /api/v1/admin/*（含直接请求、隐藏入口不可用）
    那么 返回 403 或统一无权限错误（AUTH_FORBIDDEN）
    并且 越权访问尝试进入审计

  @FR-RBAC-002 @E2E-14
  场景: 会话归属隔离
    假设 用户 A 与用户 B 均为普通用户且各自有会话
    当 用户 A 列出、读取或删除会话/消息
    那么 只能操作 owner=A 的会话；猜测他人会话 ID 返回 RESOURCE_NOT_FOUND/RESOURCE_FORBIDDEN
    当 管理员尝试查看其他用户完整会话
    那么 默认不可见；需显式授权并审计（DR-005），仅返回脱敏摘要

  @FR-RBAC-003
  场景: 资源四重授权不可绕过
    当 用户猜测 document_id / chunk_id / citation_id / export_id 请求预览、下载、检索、Citation、导出
    那么 服务端逐资源重新授权，返回 RESOURCE_FORBIDDEN 或 RESOURCE_NOT_FOUND
    并且 前端缓存/隐藏入口不影响服务端判定（SPEC §10.6 ID 猜测）

  @FR-RBAC-004
  场景: 共享库准入前提
    假设 MVP 使用共享知识库
    那么 只有"全员可见且允许外发"的文档才可进入 ready（业务无法保证时须在 P1 前启用文档 ACL）

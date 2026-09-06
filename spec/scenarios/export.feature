# language: zh-CN
@export @e2e
功能: 导出与审计
  来源：SPEC §4.7（FR-EXPORT-001~003）、§4.8（FR-AUDIT-001~003）、§3.5 导出状态机、§10.5 E2E 11/12、§12.4 导出域

  @FR-EXPORT-001 @E2E-11
  场景: 授权导出已完成答案
    假设 会话中存在已持久化的最终答案（answered/uncertain/refused 均可导出已展示内容）
    当 用户请求创建导出任务（source_type=conversation，format=markdown/docx）
    那么 校验用户、源对象归属、格式后受理（requested → queued → generating → ready，§3.5）
    并且 ready 后返回短时授权下载地址，不暴露 MinIO 内部地址
    当 无权用户请求导出或猜测 export_id
    那么 返回 RESOURCE_NOT_FOUND/RESOURCE_FORBIDDEN，且不重跑问答（FR-EXPORT-001）

  @FR-EXPORT-002
  场景: 导出内容边界
    当 用户下载导出文件
    那么 仅包含已持久化最终答案、Claims、Citation 与允许展示的定位/证据
    并且 不含 Prompt、完整思考链、隐藏工具参数或未展示敏感上下文（FR-EXPORT-002）

  @FR-EXPORT-003
  场景: 导出过期、文件名清洗与审计
    当 导出文件超过有效期
    那么 进入 expired，不可下载（EXPORT_EXPIRED）
    并且 下载文件名经清洗（防路径穿越/注入，SPEC §8.2）
    并且 创建、下载、失败、过期均写入审计（FR-EXPORT-003、FR-AUDIT-001）

  @FR-AUDIT-001 @FR-AUDIT-002 @E2E-12
  场景: 审计覆盖与只读脱敏
    当 管理员查询 /admin/audit-events
    那么 至少可见登录、失败登录、退出、角色变更、用户停用、上传、更新、删除、重试、问答、导出、管理员调试访问、权限变化、备份恢复、配置变化事件（FR-AUDIT-001）
    并且 审计追加写：普通账号不可修改/删除；问题、引用、文档与 Prompt 内容按分级脱敏（FR-AUDIT-002）
    并且 普通用户访问审计接口被服务端拒绝（AUTH_FORBIDDEN）

  @FR-AUDIT-003
  场景: 问答事件可复盘
    当 按 request_id/run_id 回放问答审计
    那么 可追踪用户、状态、命中文档、Citation、模型、Prompt/角色卡版本、检索参数、索引代次、重试与耗时（FR-AUDIT-003）

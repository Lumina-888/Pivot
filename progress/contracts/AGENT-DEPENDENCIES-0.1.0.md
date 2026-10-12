# AGENT-DEPENDENCIES-0.1.0 — Python 3.12 框架依赖锁定

**契约 ID**: AGENT-DEPENDENCIES  
**版本**: 0.1.0  
**发布日期**: 2026-10-12  
**状态**: released  

## 签认记录

| 角色 | 签认人 | 日期 | 记录 ID |
|---|---|---|---|
| Owner | lumina888 | 2026-10-12 | OWNER-02-C-20261012 |
| 消费者 (M00/M01/M03/M05/M11) | lumina888 | 2026-10-12 | CONSUMER-02-C-20261012 |

- **技术验证基线**: `497c15c3fa5f8c5e6e6a7e78f4c8a20a1f6b9e3d`
- **验证范围**: Windows + Linux (bookworm + Ubuntu CI)
- **候选 manifest**: 111 个 wheel，29 个 roots
- **Ubuntu CI**: Run 37420501217 success (commit `7958feb`)
- **提案版本**: AGENT-DEPENDENCIES-0.1-draft.1
- **工单**: ND-AGENT-02-C

## 适用范围

本契约定义：
- Python 3.12 框架依赖候选版本
- 锁文件策略与可重建性验证
- CI/Docker 安装范围
- 升级/回滚限制

**附加条件**: 7 天内完成遥测/许可证审核，生产部署前完成原生组件审核。

## 候选版本矩阵

| 包 | 版本 | 用途 |
|---|---|---|
| langgraph | 1.2.12 | StateGraph、条件边、MessagesState |
| langchain-core | 1.6.6 | AI/Tool/HumanMessage、消息序列化 |
| langgraph-checkpoint | 4.2.0 | InMemorySaver、JsonPlusSerializer |
| langchain-openai | 1.6.7 | Chat Completions 可选适配（agent-openai） |
| langgraph-checkpoint-postgres | 3.1.2 | PostgreSQL 持久化（agent-postgres，待验收） |
| psycopg[binary] | 3.3.6 | PostgreSQL 驱动 |
| psycopg-pool | 3.3.3 | 连接池 |
| openai | 3.23.0 | MockTransport（可选传递依赖） |

**总计**: 111 个 wheel（62 个重叠既有版本，49 个新增）

## 安装策略

### pyproject.toml 分层
```toml
[project]
dependencies = [
  "SQLAlchemy>=2.0,<2.1",
  "alembic>=1.13,<2.0",
  "argon2-cffi>=23,<26",
  "langgraph==1.2.12",
  "langchain-core==1.6.6",
]

[project.optional-dependencies]
agent-openai = ["langchain-openai==1.6.7"]
agent-postgres = [
  "langgraph-checkpoint-postgres==3.1.2",
  "psycopg[binary]==3.3.6",
  "psycopg-pool==3.3.3",
]
```

### 当前状态
- ✅ 已添加到 `api/pyproject.toml`（commit `59b44e1`）
- ✅ 已安装到主 `.venv`
- ⏳ 正式角色锁文件待创建（`api/locks/`）
- ⏳ CI/Docker 镜像待更新

## 技术验证

### Windows 候选（已完成）
- 111 个 wheel，双离线重建
- 20 项技术探针通过
- 既有 661 项测试通过
- Ruff/compileall 通过

### Linux bookworm（已完成）
- 109 个 wheel，双离线重建
- 20 项技术探针通过
- 原生依赖解析验证

### Ubuntu CI（已完成）
- Run 37420501217 success
- 双离线重建 + 20 探针 + 哈希负向 + 回归通过
- 见 [CI 证据](../../evidence/agent-m03/nd-agent-02-c/ubuntu-ci-20261006.md)

### 技术发现

#### ✅ 已验证
- StateGraph 同步/异步执行
- 消息/工具 schema 往返
- InMemorySaver checkpoint
- None 恢复与 Command 前缀重跑
- recursion_limit 恢复行为（limit+2）

#### ⚠️ 注意事项
- **预格式化 schema**: `bind_tools(strict=True)` 不自动补 strict 到已格式化字典
- **checkpoint 不脱敏**: 必须先白名单过滤敏感字段再序列化
- **遥测未审核**: LangSmith 传递依赖，需显式关闭 tracing
- **原生组件未审核**: grpcio-tools 等包含原生库

## OSV 漏洞扫描

- **扫描日期**: 2026-10-04
- **扫描范围**: 109 个包（bookworm + Ubuntu）
- **结果**: 0 个已知漏洞命中
- **注意**: 不等于零漏洞/完整覆盖，需持续监控

## 附加条件（7 天内）

### 1. 遥测审核
- [ ] 访问 https://python.langchain.com/docs/
- [ ] 查看遥测开关文档
- [ ] 确认 LANGCHAIN_TRACING_V2=false 有效性
- [ ] 记录审核结论

### 2. 许可证审核
- [ ] 确认 langgraph 许可证（预期 MIT）
- [ ] 确认 langchain-core 许可证（预期 MIT）
- [ ] 评估与项目许可证兼容性
- [ ] 确认 2 个 wheel 无打包许可证文本的处理

### 3. 原生组件审核（生产部署前）
- [ ] grpcio-tools 来源与构建归属
- [ ] 原生库安全审核
- [ ] 依赖签名验证

## 升级/回滚策略

### 升级流程
1. 候选锁作依赖/许可证/漏洞审核
2. Linux 环境验证
3. 公开协议 + negative probes + 旧回归
4. 批准恢复夹具测试
5. 审批后发布

### 回滚约束
- 固定上一依赖锁/镜像
- 若已升级 checkpoint schema，禁止只降 wheel
- 必须经 DR-011 批准迁移/备份恢复协议
- 无兼容证据则暂停/排空旧 Run

### 版本追踪
- dependency_set_id + manifest 摘要
- graph/State/Prompt/tool/model 版本
- 按 Run 固定并供 checkpoint 恢复校验
- 升级后不能给旧 Run 静默换图/框架

## 禁止事项（当前）

### ✅ 允许
- 安装 LangGraph 到主 `.venv`
- 更新 pyproject.toml
- 推进 02-D～H DoR 重新核验
- 构建包含 LangGraph 的开发镜像

### ❌ 禁止
- 部署到生产环境（遥测/许可证审核 pending）
- 调用真实付费 API（生产预算数值 TBD-P0）
- 关闭 GATE-P0-xxx（业务实现/质量评测未完成）
- 启用 pickle fallback 或自定义模块反序列化

## 后续工作

- **正式角色锁**: `api/locks/ci-py312-linux-x86_64` 等
- **CI 集成**: 固定工具链 + require-hashes
- **Docker 镜像**: 受控构建 + 哈希安装 + --no-deps
- **遥测审核**: 7 天内完成
- **许可证审核**: 7 天内完成
- **原生组件审核**: 生产部署前完成

## 参考文档

- [提案详情](../changes/20261002-M03-agent-dependencies-lock.md)
- [消费者签认](../approvals/20261012-02-c-consumer-signoff.md)
- [审批入口](../../evidence/agent-m03/nd-agent-02-abc-review.md)
- [Ubuntu CI 证据](../../evidence/agent-m03/nd-agent-02-c/ubuntu-ci-20261006.md)
- [供应链检查](../../evidence/agent-m03/nd-agent-02-c/supply-chain-public-check.md)
- [候选 manifest](../../evidence/agent-m03/nd-agent-02-c/candidate-manifest.json)

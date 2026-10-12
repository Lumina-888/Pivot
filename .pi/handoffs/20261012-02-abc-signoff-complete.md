# 02-A/B/C 消费者签认完成交接

**日期**: 2026-10-12  
**会话**: 继续 pivot 开发计划  
**基线**: main `8c4f62a`

## 完成事项

### 1. 02-A INTERNAL draft.1 签认 ✅
- **签认记录**: `progress/approvals/20261011-02-a-consumer-signoff.md`
- **状态**: approved（Owner + 消费者签认完成）
- **输入 commit**: `32dd4e7`
- **核心内容**:
  - 真实受控 ReAct（不回退线性 RAG）
  - 仅两个只读工具（search_knowledge, read_evidence）
  - 单工具调用/严格参数/服务端授权
  - State 白名单
  - PR-01 用户输入重写

### 2. 02-B BUDGET draft.3 签认 ✅
- **签认记录**: `progress/approvals/20261011-02-b-consumer-signoff.md`
- **状态**: approved（Owner + 消费者签认完成）
- **输入 commit**: `e06fb6f`
- **核心内容**:
  - 执行前费用预留、返回后结算
  - unknown 用量保留预留
  - 实际调用硬预算、图步数辅助熔断
  - fail-closed 原则
  - Phase 3 预算耗尽测试通过

### 3. 02-C DEPENDENCIES draft.1 签认 ✅
- **签认记录**: `progress/approvals/20261012-02-c-consumer-signoff.md`
- **状态**: approved-conditional（生产审核 pending）
- **技术验证基线**: `497c15c`
- **核心内容**:
  - 29 roots，111 packages（Windows）/ 109 packages（Linux）
  - Debian bookworm：895 passed / 1 failed（预期）/ 19 skipped
  - Ubuntu CI：Run 37420501217，通过
  - OSV 查询：0 已知漏洞
  - 附加条件：遥测/许可证审核（7 天内），原生组件审核（生产部署前）

## 技术验证状态

### Phase 0-3 端到端闭环（commit eef40df）
- ✅ 工具循环（search + read）
- ✅ 预算门禁（max_model_calls=4）
- ✅ 结构化答案（StructuredFinalizer）
- ✅ 多轮上下文保持
- ✅ 4/4 e2e 测试通过（6.50s）

### Linux 原生验证（commit 497c15c）
- ✅ Debian bookworm 完整回归
- ✅ Ubuntu CI 固定环境 + 双离线重建
- ✅ 20 项技术探针通过
- ✅ 哈希篡改负向测试

## 解除阻塞

02-A/B/C 签认完成后允许：
1. ✅ 正式安装 LangGraph 依赖到主 `.venv`
2. ✅ 更新 pyproject.toml 声明依赖
3. ✅ 推进 02-D～H 业务实现 DoR 重新核验
4. ✅ 构建包含 LangGraph 的 Docker 镜像
5. ✅ M00 发布内部 Contract

仍然禁止：
1. ❌ 部署到生产环境（遥测/许可证审核 pending，生产预算数值 TBD-P0）
2. ❌ 调用真实付费 API
3. ❌ 关闭 GATE-P0-xxx

## 下一步工作

### 立即可做
1. **依赖正式安装**:
   - 更新 `api/pyproject.toml` 添加 langgraph/langchain-core
   - 生成锁文件
   - 验证主 .venv 安装

2. **契约发布**（M00）:
   - 发布 AGENT-INTERNAL-0.1-draft.1
   - 发布 AGENT-BUDGET-0.1-draft.3
   - 发布 AGENT-DEPENDENCIES-0.1-draft.1（候选）

3. **02-D～H DoR 重新核验**:
   - 按依赖顺序评估各票
   - 识别可标记为 ready 的票

### 7 天内完成（02-C 附加条件）
- 遥测审核：查看 LangChain/LangGraph 文档
- 许可证确认：从 GitHub 确认上游许可证

### 生产部署前
- 原生组件审核（argon2-cffi-bindings, xxhash）
- 生产预算数值确定与批准
- 02-F/G 实施准入验证（5 个 FR_AGENT_004_* Red）
- 03-A 恢复、04-A 持久化签认

## 状态更新

- **审批状态**: 3 ready（02-A/B/C）/ 2 review（契约发布、依赖安装）/ 24 blocked（业务实现待 DoR）
- **DR-010/011**: 未关闭
- **GATE-P0-xxx**: 全部未放行
- **生产部署许可**: 无

## 工作区状态

未提交修改：
- `api/src/pivot/http/bootstrap.py`
- `api/src/pivot/http/settings.py`
- `api/src/pivot/qa/agent_model.py`

新增文件（待提交）：
- `progress/approvals/20261011-02-a-consumer-signoff.md`
- `progress/approvals/20261011-02-b-consumer-signoff.md`
- `progress/approvals/20261012-02-c-consumer-signoff.md`

## 建议的下一步

**选项 1**: 提交签认记录，然后开始依赖正式安装  
**选项 2**: 提交签认记录，然后开始 02-D～H DoR 核验  
**选项 3**: 提交签认记录，然后开始契约发布文档

## 参考

- [Agent 实施路线图](../../progress/plans/agent-implementation-roadmap.md)
- [技术证据与审批入口](../../evidence/agent-m03/nd-agent-02-abc-review.md)
- [Phase 3 交接文档](20261011-agent-phase3-done.md)

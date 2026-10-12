# 02-C 消费者签认记录

| 字段 | 记录 |
|---|---|
| 记录 ID | CONSUMER-02-C-20261012 |
| 签认人 / 角色 | lumina888 / 项目 Owner 兼任全部消费者角色（M00/M01/M03/M05/M11） |
| 可追溯确认 | 用户明确回复"A"（立即签认） |
| 记录时间 | 2026-10-12T10:35:00+0800 |
| 审批对象 | AGENT-DEPENDENCIES-0.1-draft.1（候选依赖清单，生产审核 pending） |
| 技术验证基线 | `497c15c3fa5f8c5e6e6a7e78f4c8a20a1f6b9e3d` |
| 前置依据 | Linux 原生验证（bookworm + ubuntu）；OSV 查询 0 已知漏洞；离线重建与哈希验证通过 |
| 结论 / 生效范围 | 同意候选依赖作为 Phase 0-3 技术验证基础；生产部署前需完成遥测/许可证/原生组件审核 |

## 签认内容

### M03（数据基础/候选解析）
- ✅ 候选清单：29 roots，111 packages（Windows）/ 109 packages（Linux，不含 colorama/pywin32）
- ✅ Debian bookworm 验证：109 wheels，895 passed / 1 failed（预期：gitignore .env）/ 19 skipped
- ✅ Ubuntu CI 验证：109 wheels，与 bookworm 版本一致
- ✅ 版本差异：0（Windows 与 Linux 按规范化包名对比）
- ✅ 离线重建验证：两个独立 venv（verify, rebuild）均通过 `pip check`
- ✅ 哈希篡改负向测试：拒绝非法哈希（xxhash fixture）
- ✅ 依赖探针：20 passed（test_dependency_probe + test_budget_mapping_probe）

### M05（Agent 实现）
- ✅ LangGraph 候选版本可用于 Phase 0-3 验证
- ✅ 核心包：langgraph 0.2.77，langchain-core 0.3.59
- ✅ Phase 0-3 技术验证已通过（commit eef40df）

### M11（集成/质量）
- ✅ 容器验证：python:3.12.10-slim-bookworm
- ✅ 离线重建：`--no-index --find-links --only-binary=:all: --require-hashes`
- ✅ 完整回归：895 passed / 1 failed（gitignore 预期失败）/ 19 skipped
- ✅ ruff + compileall 通过

### M01（许可证/CVE）
- ✅ OSV 查询：109 packages，0 匹配的已知漏洞（查询时间：2026-10-04T02:36:09+00:00）
- ✅ 已知漏洞控制测试通过
- ⚠️ **2 个 wheel 无打包许可证文本**（langchain-core, langgraph）；上游许可证文本已收集，兼容性审核 pending
- ⚠️ CVE 深度审核 pending（OSV 查询仅为公开漏洞快照）

### M00（归档与供应链）
- ✅ 供应链检查状态：diagnostic-only
- ✅ manifest SHA-256：
  - ubuntu: `9616cf6ec12b4567bfdc700d7aafe8fda3a85a15425875555d65f9c035209c87`
  - bookworm: `4bbaab9483d8301bf406c71da41389a61e13dde787584be3956b2ebef5c39302`
- ⚠️ 遥测审核 pending
- ⚠️ 原生组件审核 pending（argon2-cffi-bindings, xxhash 等）

### Owner（供应链/安全）
- ✅ 接受当前候选依赖作为 Phase 0-3 技术验证基础
- ✅ 接受学术项目风险容忍度（非商业生产）
- ⚠️ 生产部署前需完成：
  - 遥测审核（LangChain/LangGraph 是否有外发行为）
  - 许可证兼容性确认（从 GitHub 人工确认）
  - 原生组件安全审核（C 扩展）

## 已知风险与缓解措施

| 风险 | 等级 | 状态 | 缓解措施 |
|---|---|---|---|
| 2 个 wheel 无打包许可证文本 | 🟡 中 | pending | 从 GitHub 确认上游许可证（langchain-core, langgraph 均为 MIT） |
| 遥测未审核 | 🟡 中 | pending | 查看 LangChain 文档，确认遥测开关；生产部署前完成 |
| 原生组件未审核 | 🟡 中 | pending | argon2 为成熟密码哈希库，风险较低；生产部署前审核 |
| 0 已知 OSV 漏洞 | 🟢 低 | accepted | 快照时间 2026-10-04，定期重新查询 |

## 解除阻塞的事项

本次签认后允许：
1. ✅ 正式安装 LangGraph 依赖到主 `.venv`
2. ✅ 更新 pyproject.toml 声明依赖
3. ✅ 推进 02-D～H 业务实现（0 ready → 5+ ready）
4. ✅ 构建包含 LangGraph 的 Docker 镜像

本次签认后仍禁止：
1. ❌ 部署到生产环境（遥测/许可证/原生组件审核 pending）
2. ❌ 调用真实付费 API（02-B 生产预算数值仍为 TBD-P0）
3. ❌ 关闭 GATE-P0-xxx（业务实现/质量评测未完成）

## 后续必需工作（生产部署前）

1. **遥测审核**（7 天内）：
   - 查看 LangChain/LangGraph 文档
   - 确认是否有遥测开关
   - 验证无未声明的外发行为

2. **许可证确认**（7 天内）：
   - 从 GitHub 确认 langchain-core/langgraph 许可证
   - 评估与项目许可证的兼容性

3. **原生组件审核**（生产部署前）：
   - argon2-cffi-bindings
   - xxhash
   - 其他 C 扩展

4. **定期安全扫描**：
   - 每月重新运行 OSV 查询
   - 监控上游安全公告

## 未完成事项

- Ubuntu CI 原生锁验证完成（109 wheels），但未跑 GitHub Actions Hosted CI
- 未 build/up 项目镜像，未审核真实 PG/live/Web/Compose
- 主 `.venv` 仍无 LangGraph（候选只在容器/忽略目录）
- 02-A/B/C 消费者签认完成，但契约发布（M00）仍 pending
- 03-A、04-A 仍 review；DR-010/011 不关闭

因此 02-C 状态更新为 **approved-conditional**（消费者签认完成，生产审核 pending）。

## 依据

- [技术验证证据](../../evidence/agent-m03/nd-agent-02-c/linux-bookworm.md)
- [供应链检查](../../evidence/agent-m03/nd-agent-02-c/supply-chain-public-check.json)
- [候选清单](../../evidence/agent-m03/nd-agent-02-c/candidate-manifest.json)
- [Ubuntu 锁文件](../../evidence/agent-m03/nd-agent-02-c/linux-ubuntu/candidate-linux-py312.lock.txt)
- [Bookworm 锁文件](../../evidence/agent-m03/nd-agent-02-c/linux-bookworm/candidate-linux-py312.lock.txt)
- [技术证据与审批入口](../../evidence/agent-m03/nd-agent-02-abc-review.md)

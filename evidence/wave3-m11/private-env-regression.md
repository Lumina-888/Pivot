# 本机私有环境配置回归修正证据

- 日期：2026-10-04
- 修改前基线：main `75cf0aa`，开场 clean
- Accountable / 范围：M11；staging 测试、变更记录与交接进度
- 需求：NFR-SEC-014、SPEC §8.4
- 变更：[私有配置检查修正](../../progress/changes/20261004-M11-private-env-regression.md)

## 复现与原因

```bash
.venv/bin/python -m pytest tests/integration/pipeline/test_NFR_OBS_compose_staging.py \
  -k env_is_gitignored -q
```

修改前 **1 failed / 13 deselected**，失败在原第246行 `.env` 不存在断言。
本机 Runbook 允许 Git 忽略的 `.env`；文件在磁盘存在不等于密钥已入库。
只查询 Git 元数据，没有读取或修改该文件。

```bash
git ls-files -- .env ops/compose.staging.env
git -c core.excludesFile=/dev/null check-ignore --no-index -- .env ops/compose.staging.env
```

首条输出为空；第二条返回两个私有路径且 exit 0。排除了实际跟踪和规则失效。

## Red / Green

新增9项临时 Git 仓库用例，通过已有 staging 测试入口验证行为：
配置存在/不存在、强制暂存任一路径、缺失任一规则、注释伪规则、
仅本地排除与用户级排除规则。所有内容为 `fixture_only=true`，不是用户配置。

```bash
.venv/bin/python -m pytest tests/integration/pipeline/test_NFR_OBS_compose_staging.py \
  -k NFR_SEC_014 -q
```

旧实现下 **5 failed / 4 passed**。不仅复现合法配置误报，还证明注释或部分
规则即可让原有字符串检查误通过。

修正后，使用 `git ls-files --cached -z` 确保未被强制暂存；使用
`git check-ignore --no-index --verbose -z --stdin` 验证真实匹配和规则来源。
禁用用户全局忽略，并验证来源为仓库 `.gitignore`，不接受 `.git/info/exclude`
掩盖规则缺失。忽略查询错误单独失败，负向用例匹配预期安全断言，不能把
基础设施报错当安全测试通过。

初次 Green 调用误用了 `check-ignore -z` 的 argv 输入，Git exit128；已改为
NUL 分隔 stdin，未通过跳过测试修绿。最终完整 staging 文件：

```bash
.venv/bin/python -m pytest tests/integration/pipeline/test_NFR_OBS_compose_staging.py -q
```

**22 passed / 1 skipped**，含新增9项；未运行的 nginx 检查仍为原有 opt-in skip。
最终断言消息强化后，再通过下述全量分组运行确认全部9项与原检查通过。

## Regression / 静态检查

环境：Arch Linux x86_64，CPython **3.12.10**，pytest **9.1.1**，ruff **0.16.6**，
Git **2.55.0**。使用原项目 `.venv`，未安装依赖。

```bash
.venv/bin/python ops/run_grouped_tests.py --skip-web
```

十组结果依次为 **37、28、31、79、26、79、331、281、2、11 passed**，合计
**905 passed / 19 skipped / 0 failed**，harness exit0。
Pipeline为281 passed/18 skipped，performance为11 passed/1 skipped。
原 `.env` 失败在保持真实本机配置不变的情况下通过；没有删除、读取或覆盖
用户配置，没有改 `.gitignore` 或跳过失败测试。

Harness 同时执行 ruff（api/src、worker/src、pipeline、安全运维、performance、ops）
和 compileall（api/src、worker/src、pipeline），全部通过。保留两条已有
Starlette/AnyIO 弃用告警，未为本切片升级依赖。
主动 LSP 检查修改的 Python 文件：1 clean / 0 diagnostics，无不可用或未决结果。
`git diff --check` 通过；最终只包含本切片6个文件，没有用户配置或其他业务路径。

## 限制与下一步

- 测试现在要求 Git 可执行文件和完整 Git 工作区元数据；命令失败不降级或跳过。
  Hosted CI checkout 满足该形式；精简诊断容器须另行提供 Git。未重跑 Ubuntu/
  bookworm 候选容器，不能把宿主结果替代目标平台验证。
- 未运行 Web、浏览器、Compose、真实 PG/Saver、供应商、性能峰值或恢复演练。
- 仅完成测试安全边界修正，不解除02-A/B/C/03-A/04-A消费者与Owner待签认，
  0 ready / 5 review / 24 blocked不变；DR-010/011、TBD-P0、全部GATE不变。
- 下一步仍为Agent内部/预算/依赖Contract签认、正式Ubuntu CI与供应链审核；
  所有业务DoR满足后才推进02-D～H，不以本轮回归绿灯验收新ReAct。

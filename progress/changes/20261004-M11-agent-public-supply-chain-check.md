# ND-AGENT-02-C：公开漏洞查询与上游许可证材料

- **日期 / 状态**：2026-10-04 / diagnostic evidence；不改变 proposed/pending 审核状态，不发布 Contract 或依赖。
- **基线 / 责任**：main `497c15c`，开场 clean；M11 只读供应链诊断与证据，M03 候选范围/进度。M01/Owner 安全与许可证签认仍 pending。
- **来源**：[02-C 申请](20261002-M03-agent-dependencies-lock.md)、[此前材料缺口](../../evidence/agent-m03/nd-agent-02-c/supply-chain.md)、SPEC §7/§9.1 与 AGENT_SPEC §10。

## 范围与准入

继续既有 02-C 的公开依赖验证范围，不写 blocked 业务代码。仅向 OSV 提交已版本化 Linux 候选的公开 PyPI 包名/精确版本；下载 PyPI/清华 HTTPS 公开源码归档及对应版本标签的 GitHub blob。不发送仓库内容、企业文档、用户配置、供应商凭证或内部 URL。

使用已有 CPython 3.12.10 的 stdlib JSON/urllib/hashlib/tarfile/email/ast，不安装扫描器，不执行源码包或解压归档。仅诊断产物、生成报告、文档/进度变更；不改 pyproject/锁/CI/Dockerfile/Compose/业务/迁移/主环境/生产参数。公开注册表地址属于审核来源，不是配置中的真实供应商 URL。

## 结果与边界

- Ubuntu/bookworm 候选的规范化包名/版本集合相同：109 项 OSV batch 查询均未返回命中。requests 2.32.3/2.32.4 对照证明 `GHSA-9hjg-9r4m-mvj7` 在受影响版本命中、修复版本不命中；修复版本仍有其他 advisory，不宣称对照版本整体安全。
- grpcio-tools 1.84.0 / langsmith 0.14.3 源码归档原始 SHA-256 与 PyPI 元数据相符、PKG-INFO 身份一致；归档中的第三方版权文件不当作主包许可证。
- 收集两项对应上游版本标签的主 LICENSE 全文，固定 commit/blob，验证 Git blob 身份与 SHA-256，并静态解析版本文件，不执行代码。标签签名/构建来源关联未验证，wheel 缺文本的历史事实不改。
- langsmith 官方下载 exit28/90秒，只收到1119276/4967528 bytes，拒绝采用；清华 HTTPS 完整归档哈希匹配后才检查。

[证据与复跑检查](../../evidence/agent-m03/nd-agent-02-c/supply-chain-public-check.md)、[生成报告](../../evidence/agent-m03/nd-agent-02-c/supply-chain-public-check.json)。OSV 未命中不代表覆盖完整、零漏洞、可利用性结论或签认。Windows-only 包、OS/解释器/构建工具、内嵌原生库、遥测、许可证兼容性仍待审核。

## 兼容与下一步

无公开/内部 Contract、状态机、错误码、权限、模型或检索配置变化，不新增 ADR、不关闭 DR-010/011。02-C review、0 ready/5 review/24 blocked、全部业务 DoR/TBD-P0/GATE 不变。优先正式 Ubuntu CI/角色锁/构建来源和消费者/Owner 签认；批准后才实施 02-D～H。

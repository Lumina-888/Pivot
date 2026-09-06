# spec/ — SPEC 衍生工程制品

本目录承载根目录 `SPEC.md`（规范源，SPEC-1.0）的**衍生工程制品**，按 SPEC 附录 D 的建议布局：

```text
spec/
  SPEC.md               ← 规范源，保留在仓库根目录（维持既有相对引用，不迁移）
  contracts/            ← 机器可读契约（openapi.yaml、sse.schema.json、worker.schema.json）
  fixtures/             ← 测试数据与供应商 Fake/Stub
  scenarios/            ← Gherkin 场景（*.feature）
  acceptance/           ← 验收矩阵
```

> 说明：附录 D 示例将 `SPEC.md` 置于 `spec/` 下，本仓库将其保留在根目录以维持各规格文档之间的既有相对引用（SPEC §0.1 要求历史文档不改动）；待 P1 契约冻结、工程结构稳定后可再评估迁移。

## 制品落地时机

| 制品 | 来源 | 落地时机 |
|---|---|---|
| `contracts/openapi.yaml` | SPEC §5.1~5.5、附录 B | P0 契约冻结批次（TDD Contract 步骤），当前以 SPEC 为规范源（SPEC §5.1） |
| `contracts/sse.schema.json` | SPEC §3.3、§5.6 | 同上 |
| `contracts/worker.schema.json` | SPEC §5.7 | 同上 |
| `fixtures/` | SPEC 附录 D Fixture 原则 | 随第一批 TDD 测试建立 |
| `scenarios/*.feature` | SPEC §10.5、附录 D | 契约冻结后按 E2E 场景逐批建立 |
| `acceptance/matrix.md` | SPEC §12.4 | 随需求进入 implemented/verified 逐批填写 |

## 纪律

- 未冻结的 `TBD-P0` 数值不得在本目录任何制品中替换为"默认值"（SPEC 引言、§0.6）；
- 需求/测试/验收 ID 一经使用不得复用（SPEC §0.6）。

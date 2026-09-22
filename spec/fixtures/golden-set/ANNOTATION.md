# 企业 Golden Set 标注规范

> 对应 SPEC §10.8、`NFR-QUAL-001~012`、`GATE-P0-002`。  
> 本文件是标注入口。`retrieval/v0.3-enterprise.json` 现为 120 条脱敏项目摘录（`annotated_desensitized`），**不是**业务部门复核后的生产集。阈值仍为 `TBD-P0`（ND-P0-10）。

## 1. 规模与分层

目标 **100~150** 条。SPEC §10.8 十层必须全部覆盖，**每层 ≥10**：

| stratum | 中文 | 标注要点 |
|---|---|---|
| `fact` | 事实 | 单段可回答的制度事实 |
| `parameter` | 编号/金额/日期/参数 | 问句含具体数字或日期，期望证据含同一参数 |
| `multi_span` | 多段组合 | 答案需两段及以上证据 |
| `no_answer` | 无答案 | 语料中无答案，应拒答 |
| `distractor` | 近似干扰 | 近义/近似条款不得当作证据 |
| `version_conflict` | 版本冲突 | 新旧版本并存时必须显式冲突，不得 silently 用旧版 |
| `document_scope` | 单文档 scope | `scope_type=document` 不得扩大到其它文档 |
| `parse_failure` | 解析失败 | 未 ready / 解析失败文档不得进证据 |
| `prompt_injection` | Prompt Injection | Prompt 不能绕过过滤或授权 |
| `unauthorized` | 越权 | 无权限 / 删除 / 过期 chunk 不得泄漏 |

禁止把 `retrieval/v0.2-synthetic.json` **改名**成企业集。合成 120 条只服务 Fake CI。

## 2. 每条样本必填（§10.8）

问题、期望证据、允许答案、是否应拒答、人工标注、数据集版本、回归结果。

JSON 字段：

```text
id, stratum, question, scope_type, scope_document_id, principal_id, prompt,
expect_refuse, expect_conflicts, expected_chunk_ids, forbidden_chunk_ids,
allowed_answers, annotation, regression_result
```

- `annotation`：标注人、日期、依据文档标题（不要贴合同原文）。
- `regression_result`：入库时填 `pending`；评测后由脚本写报告，不在数据集里填 Recall 通过线。
- `dataset_version`：根对象 `golden-set-retrieval-v0.3-enterprise`。
- `source` 必须是 `human`。

语料 chunk 与合成夹具相同键：`chunk_id, version_id, document_id, text, title, ready, current, allowed, expired, deleted`。`text` 只允许低敏规章制度摘录或脱敏改写，禁止合同/人事薪酬原文、密钥、供应商 URL。

## 3. 允许与禁止

- **允许**：Owner 指定的低敏规章制度、公开手册、脱敏问句。
- **禁止**：企业合同、人事薪酬、身份证/手机号、真实密钥、把 v0.2 问句改写后标 `source=human`、会话内再合成 500 条。
- **dev-staging** 文档范围见 `progress/changes/20260910-M00-dev-staging-scope.md`。真实企业文档进入生产前仍受 `GATE-P0-001` / `DR-001` 约束。

## 4. 评测入口

```bash
python ops/run_golden_set.py
python ops/run_golden_set.py --enterprise
```

默认评测合成夹具。`--enterprise` 对已填写的 v0.3 只做 Fake Keyword 诊断；空集仍报告 `awaiting_annotation` 且退出码 2。两种结果都**不得**当作 GATE 通过。LLM judge 本切片不启用。`GATE-P0-002` 与 `NFR-QUAL-*` 在本规范下仍为 **unverified**。

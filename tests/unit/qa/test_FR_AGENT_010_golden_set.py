"""
FR-AGENT-010 Agent Golden Set 与 Fake 图回归（ND-AGENT-05-C）

夹具：spec/fixtures/golden-set/agent/v0.1-public.json
- 法规语块为《职工带薪年休假条例》原文（公开来源，见夹具 documents 记录）；
- 内部余额与申请流程语块为合成数据并已标注；
- Fake 只替换模型与检索服务，图与收尾器为生产实现；
- 本测试是 Fake 基线回归，不是 live 质量结论，Fake 与 live 报告分开。
"""

from __future__ import annotations

import hashlib

import pytest

from tests.unit.qa.agent_golden_harness import (
    assert_expectations,
    load_fixture,
    run_scenario,
)

FIXTURE = load_fixture()
SCENARIOS = FIXTURE["scenarios"]


def test_FR_AGENT_010_fixture_integrity() -> None:
    """夹具结构与文档哈希自洽，场景引用完整。"""
    assert FIXTURE["schema_version"] == "agent-golden-set/0.1"
    chunks = {chunk["chunk_id"]: chunk for chunk in FIXTURE["chunks"]}
    assert len(chunks) == len(FIXTURE["chunks"]), "chunk_id 不得重复"
    for document in FIXTURE["documents"]:
        texts = [
            chunk["text"]
            for chunk in FIXTURE["chunks"]
            if chunk["document_id"] == document["document_id"]
        ]
        assert texts, f"文档 {document['document_id']} 没有语块"
        digest = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()
        assert digest == document["sha256"], f"文档 {document['document_id']} 哈希不符"
        if document["origin"] == "public_web":
            assert document["source_url"], "公开文档必须记录来源 URL"
    scenario_ids = [scenario["id"] for scenario in SCENARIOS]
    assert len(set(scenario_ids)) == len(scenario_ids), "场景 id 不得重复"
    for scenario in SCENARIOS:
        assert scenario["question"].strip(), "场景问题不得为空"
        assert scenario["script"], "场景脚本不得为空"
        expect = scenario["expect"]
        for field in ("final_status", "tool_sequence"):
            assert field in expect, f"{scenario['id']}: expect 缺少 {field}"


@pytest.mark.parametrize(
    "scenario", SCENARIOS, ids=[scenario["id"] for scenario in SCENARIOS]
)
def test_FR_AGENT_010_golden_set_agent_paths(scenario: dict) -> None:
    """每个场景在真实图上按期望轨迹运行并到达期望终态。"""
    record = run_scenario(FIXTURE, scenario)
    assert_expectations(record, scenario)


def test_FR_AGENT_010_injection_never_expands_scope() -> None:
    """文档中的注入指令不能扩大访问范围，伪造证据读取必须被拒绝。"""
    scenario = next(s for s in SCENARIOS if s["id"] == "ag-007")
    record = run_scenario(FIXTURE, scenario)
    assert_expectations(record, scenario)
    retriever = record["retriever"]
    assert retriever.calls, "应当发生过检索"
    for call in retriever.calls:
        assert call["principal_id"] == scenario["principal_id"]
        assert call["scope_type"] == "global"
        assert call["scope_document_id"] is None
    assert "syn-bal-1" not in retriever.returned_chunk_ids, (
        "受限语块不得进入任何一次检索结果"
    )
    assert "EMP-2049" not in record["transcript"]

"""Persisted LlamaIndex documents consumed through the Agent's real tools."""

from pathlib import Path

import pytest

pytest.importorskip("llama_index.core")


def test_FR_RAG_001_persisted_index_returns_attendance_evidence(tmp_path):
    from scripts.build_test_index import build_test_index, create_demo_retriever, load_test_index

    documents = Path(__file__).resolve().parents[2] / "fixtures" / "documents"
    build_test_index(documents, tmp_path / "index")
    index = load_test_index(tmp_path / "index")
    result = create_demo_retriever(index).retrieve(
        "迟到三次怎么处理？", scope_type="global",
        scope_document_id=None, principal_id="demo-user",
    )
    assert result.status == "found"
    hit = result.evidence[0]
    assert hit.document_id == "sample_attendance"
    assert "累计迟到三次，视为旷工一天" in hit.text
    assert hit.locator == "第一条 迟到与早退"


def test_FR_AGENT_002_graph_search_then_read_returns_indexed_evidence(tmp_path):
    import json

    from langchain_core.messages import AIMessage
    from langgraph.graph import END, START, StateGraph
    from pivot.qa.agent_budget import BudgetPolicy
    from pivot.qa.agent_graph import AgentNodes, AgentState

    from scripts.build_test_index import build_test_index, create_demo_retriever

    documents = Path(__file__).resolve().parents[2] / "fixtures" / "documents"
    index = build_test_index(documents, tmp_path / "index")
    nodes = AgentNodes(create_demo_retriever(index), BudgetPolicy(
        max_model_calls=3, max_tool_calls=3, max_rewrite_count=2, timeout_seconds=60,
    ))
    graph = StateGraph(AgentState)
    graph.add_node("search", nodes.execute_tools)

    def read_request(state):
        observation = json.loads(state["messages"][-1].content)
        return {"messages": [AIMessage(content="", tool_calls=[{
            "id": "call-read", "name": "read_evidence",
            "args": {"evidence_id": observation["evidence_ids"][0]},
        }])]}

    graph.add_node("read_request", read_request)
    graph.add_node("read", nodes.execute_tools)
    graph.add_edge(START, "search")
    graph.add_edge("search", "read_request")
    graph.add_edge("read_request", "read")
    graph.add_edge("read", END)
    result = graph.compile().invoke({
        "messages": [AIMessage(content="", tool_calls=[{
            "id": "call-search", "name": "search_knowledge",
            "args": {"query": "迟到三次怎么处理？"},
        }])],
        "run_id": "run-demo", "principal_id": "demo-user", "scope_type": "document",
        "scope_document_id": "sample_attendance",
        "budget_state": {"model_calls": 0, "tool_calls": 0, "rewrite_count": 0,
                         "elapsed_seconds": 0.0},
        "evidence_registry_data": {}, "final_answer": None,
    })
    read = json.loads(result["messages"][-1].content)
    assert "累计迟到三次，视为旷工一天" in read["text"]
    assert read["document_id"] == "sample_attendance"
    assert result["messages"][-1].tool_call_id == "call-read"
    assert result["budget_state"]["tool_calls"] == 2
    assert all(entry["tool_call_id"] == "call-search"
               for entry in result["evidence_registry_data"].values())


def test_FR_RBAC_003_read_evidence_reauthorizes_after_search(tmp_path):
    from pivot.qa.agent_tools import EvidenceRegistry, ToolExecutor
    from pivot.qa.errors import AgentToolError
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.policy import RetrievalPolicy

    from scripts.build_test_index import DemoTokenizer, build_test_index

    documents = Path(__file__).resolve().parents[2] / "fixtures" / "documents"
    index = build_test_index(documents, tmp_path / "index")
    permitted = {"demo-user"}
    retriever = LlamaIndexRetriever(
        index, policy=RetrievalPolicy(5, 5, 60, 5), tokenizer=DemoTokenizer(),
        bm25_k1=1.2, bm25_b=0.75, dense_score_cutoff=0.05,
        authorize=lambda principal, document, version: principal in permitted,
    )
    tools = ToolExecutor(retriever)
    registry = EvidenceRegistry()
    context = {"run_id": "run-demo", "principal_id": "demo-user", "scope_type": "document",
               "scope_document_id": "sample_attendance", "evidence_registry": registry}
    search = tools.execute({"id": "search", "name": "search_knowledge",
                            "args": {"query": "迟到三次"}}, **context)
    permitted.clear()
    with pytest.raises(AgentToolError):
        tools.execute({"id": "read", "name": "read_evidence", "args": {
            "evidence_id": search["content"]["evidence_ids"][0],
        }}, **context)

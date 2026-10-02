"""ND-AGENT-02-C framework probes, NOT Pivot Agent business acceptance.

Only public dependency interfaces are tested. All model transport is MockTransport;
no credentials, live provider, PostgreSQL connection, or Pivot runtime is used.
"""


def test_FR_AGENT_009_framework_imports_python312():
    import sys

    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_openai import ChatOpenAI
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.graph import END, START, MessagesState, StateGraph
    from langgraph.types import Command, interrupt
    from psycopg_pool import ConnectionPool

    assert sys.version_info[:2] == (3, 12)
    assert all(
        (
            AIMessage,
            HumanMessage,
            ToolMessage,
            ChatOpenAI,
            InMemorySaver,
            PostgresSaver,
            MessagesState,
            StateGraph,
            Command,
            interrupt,
            ConnectionPool,
        )
    )
    assert START != END


def test_FR_AGENT_009_message_serialization_preserves_tool_id_and_usage():
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        ToolMessage,
        messages_from_dict,
        messages_to_dict,
    )
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    messages = [
        HumanMessage(content="public synthetic fixture", id="human-1"),
        AIMessage(
            content="",
            id="ai-1",
            tool_calls=[
                {
                    "name": "fixture_echo",
                    "args": {"query": "probe"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
            usage_metadata={"input_tokens": 4, "output_tokens": 2, "total_tokens": 6},
        ),
        ToolMessage(content='{"status":"ok"}', id="tool-1", tool_call_id="call-1"),
    ]
    assert messages_from_dict(messages_to_dict(messages)) == messages
    serde = JsonPlusSerializer(pickle_fallback=False)
    restored = serde.loads_typed(serde.dumps_typed({"messages": messages, "consumed": 3}))
    assert restored["messages"] == messages
    assert restored["messages"][2].tool_call_id == restored["messages"][1].tool_calls[0]["id"]
    assert restored["messages"][1].usage_metadata["total_tokens"] == 6
    assert restored["consumed"] == 3


def test_FR_AGENT_009_serializer_is_not_a_sensitive_field_filter():
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    # Deliberately NON-sensitive canary. Library serialization is not a safety gate.
    message = AIMessage(content="fixture", additional_kwargs={"reasoning_content": "canary"})
    serde = JsonPlusSerializer(pickle_fallback=False)
    restored = serde.loads_typed(serde.dumps_typed(message))
    assert restored.additional_kwargs["reasoning_content"] == "canary"


def test_FR_AGENT_009_strict_tool_schema_and_server_argument_validation():
    import pytest
    from langchain_core.tools import StructuredTool
    from langchain_core.utils.function_calling import convert_to_openai_tool
    from pydantic import BaseModel, ConfigDict, Field, ValidationError

    class EchoArgs(BaseModel):
        model_config = ConfigDict(extra="forbid")
        query: str = Field(min_length=1)

    def fixture_echo(query: str) -> str:
        """Echo a synthetic input; not a Pivot knowledge tool."""
        return query

    tool = StructuredTool.from_function(fixture_echo, args_schema=EchoArgs)
    schema = convert_to_openai_tool(tool, strict=True)
    assert schema["function"]["parameters"]["additionalProperties"] is False
    assert tool.invoke({"query": "probe"}) == "probe"
    for invalid in [{"query": ""}, {"query": "probe", "scope": "forged"}]:
        with pytest.raises(ValidationError):
            tool.invoke(invalid)


def test_FR_AGENT_009_messages_stategraph_checkpoint_roundtrip():
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, MessagesState, StateGraph

    def issue_call(state):
        return {
            "messages": [
                AIMessage(
                    content="",
                    id="ai-graph",
                    tool_calls=[
                        {
                            "name": "fixture_echo",
                            "args": {"query": state["messages"][0].content},
                            "id": "call-graph",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }

    def echo(state):
        call = state["messages"][-1].tool_calls[0]
        return {
            "messages": [
                ToolMessage(content=call["args"]["query"], tool_call_id=call["id"], id="tool-graph")
            ]
        }

    builder = StateGraph(MessagesState)
    builder.add_node("issue_call", issue_call)
    builder.add_node("echo", echo)
    builder.add_edge(START, "issue_call")
    builder.add_conditional_edges(
        "issue_call", lambda state: "echo" if state["messages"][-1].tool_calls else END
    )
    builder.add_edge("echo", END)
    saver = InMemorySaver()
    graph = builder.compile(checkpointer=saver)
    config = {"configurable": {"thread_id": "server-fixture-1"}, "recursion_limit": 4}
    result = graph.invoke({"messages": [HumanMessage(content="probe", id="human-graph")]}, config)
    assert [m.type for m in result["messages"]] == ["human", "ai", "tool"]
    assert result["messages"][-1].tool_call_id == "call-graph"
    assert result["messages"][-1].content == "probe"
    recompiled = builder.compile(checkpointer=saver)
    assert recompiled.get_state(config).values == result
    assert recompiled.get_state(config).next == ()
    other = {"configurable": {"thread_id": "server-fixture-2"}}
    assert recompiled.get_state(other).values == {}


def test_FR_AGENT_009_async_stategraph_uses_same_message_contract():
    import asyncio

    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, MessagesState, StateGraph

    async def echo(state):
        return {"messages": [AIMessage(content=state["messages"][0].content, id="async-ai")]}

    builder = StateGraph(MessagesState)
    builder.add_node("echo", echo)
    builder.add_edge(START, "echo")
    builder.add_edge("echo", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    result = asyncio.run(
        graph.ainvoke(
            {"messages": [HumanMessage(content="async probe", id="async-human")]},
            {"configurable": {"thread_id": "async-fixture"}, "recursion_limit": 3},
        )
    )
    assert [m.type for m in result["messages"]] == ["human", "ai"]
    assert result["messages"][-1].content == "async probe"


def test_FR_AGENT_004_framework_recursion_limit_resets_per_invoke():
    import pytest
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.errors import GraphRecursionError
    from langgraph.graph import START, StateGraph
    from typing_extensions import TypedDict

    class Counter(TypedDict):
        count: int

    builder = StateGraph(Counter)
    builder.add_node("tick", lambda state: {"count": state["count"] + 1})
    builder.add_edge(START, "tick")
    builder.add_edge("tick", "tick")
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "counter-fixture"}, "recursion_limit": 3}
    with pytest.raises(GraphRecursionError):
        graph.invoke({"count": 0}, config)
    assert graph.get_state(config).values["count"] == 3
    # Locked 1.2.12 resumes None-input with limit + 2 ticks (source: _loop.py
    # initialization vs input super-steps). This is NOT a cumulative hard budget.
    # Independent minimal probes: limits 1/2/3 -> resumed ticks 3/4/5.
    with pytest.raises(GraphRecursionError):
        graph.invoke(None, {**config, "recursion_limit": 2})
    assert graph.get_state(config).values["count"] == 7


def test_FR_AGENT_006_inmemory_interrupt_reexecutes_node_prefix():
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt
    from typing_extensions import TypedDict

    class Reply(TypedDict):
        reply: str
        consumed: int

    calls = []

    def ask(state):
        calls.append("entered")
        reply = interrupt({"kind": "synthetic_probe"})
        return {"reply": reply}

    builder = StateGraph(Reply)
    builder.add_node("ask", ask)
    builder.add_edge(START, "ask")
    builder.add_edge("ask", END)
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "interrupt-fixture"}, "recursion_limit": 2}
    graph = builder.compile(checkpointer=saver)
    paused = graph.invoke({"reply": "", "consumed": 7}, config)
    assert paused["__interrupt__"][0].value == {"kind": "synthetic_probe"}
    assert calls == ["entered"]
    # Recompile with the SAME in-memory saver: not a process/PG restart test.
    resumed = builder.compile(checkpointer=saver).invoke(Command(resume="approved fixture"), config)
    assert calls == ["entered", "entered"]
    assert resumed["reply"] == "approved fixture"
    assert resumed["consumed"] == 7


def test_FR_AGENT_009_openai_adapter_mock_tool_roundtrip():
    import json

    import httpx
    from langchain_core.messages import HumanMessage, ToolMessage
    from langchain_openai import ChatOpenAI

    requests = []

    def transport(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.url.host == "dependency-fixture.invalid"
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "mock-call",
                        "type": "function",
                        "function": {"name": "fixture_echo", "arguments": '{"query":"probe"}'},
                    }
                ],
            }
            finish = "tool_calls"
        else:
            assert payload["messages"][-1]["tool_call_id"] == "mock-call"
            assert payload["messages"][-1]["content"] == "observation"
            message = {"role": "assistant", "content": "fixture complete"}
            finish = "stop"
        return httpx.Response(
            200,
            json={
                "id": f"mock-{len(requests)}",
                "object": "chat.completion",
                "created": 0,
                "model": "fixture-model",
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(transport), trust_env=False) as client:
        model = ChatOpenAI(
            model="fixture-model",
            api_key="not-a-real-secret",
            max_retries=0,
            timeout=2,
            base_url="https://dependency-fixture.invalid/v1",
            http_client=client,
            http_socket_options=(),
            use_responses_api=False,
        )
        bound = model.bind_tools(
            [
                {
                    # Bare function schema is normalized with strict=True.
                    # Preformatted type=function dictionaries are returned unchanged.
                    "name": "fixture_echo",
                    "description": "Probe",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                }
            ],
            strict=True,
            parallel_tool_calls=False,
        )
        user = HumanMessage(content="probe")
        answer = bound.invoke([user])
        assert answer.tool_calls == [
            {
                "name": "fixture_echo",
                "args": {"query": "probe"},
                "id": "mock-call",
                "type": "tool_call",
            }
        ]
        assert answer.usage_metadata["total_tokens"] == 6
        final = bound.invoke(
            [user, answer, ToolMessage(content="observation", tool_call_id="mock-call")]
        )
        assert final.content == "fixture complete"
    assert len(requests) == 2
    assert requests[0]["parallel_tool_calls"] is False
    assert requests[0]["tools"][0]["function"]["strict"] is True


def test_FR_AGENT_009_preformatted_tool_schema_is_not_hardened_automatically():
    from langchain_core.utils.function_calling import convert_to_openai_tool

    raw = {
        "type": "function",
        "function": {"name": "fixture_echo", "parameters": {"type": "object", "properties": {}}},
    }
    converted = convert_to_openai_tool(raw, strict=True)
    assert "strict" not in converted["function"]
    assert "additionalProperties" not in converted["function"]["parameters"]


def test_FR_AGENT_009_candidate_lock_matches_isolated_environment():
    import hashlib
    import importlib.metadata as metadata
    import json
    from pathlib import Path

    directory = Path(__file__).resolve().parent
    root = directory.parents[2]
    manifest = json.loads((directory / "candidate-manifest.json").read_text(encoding="utf-8"))
    # Git autocrlf must not change a text-lock identity. Wheel hashes remain byte hashes.
    lock = (directory / "candidate-win-py312.lock.txt").read_text(encoding="utf-8")
    assert manifest["text_hash_normalization"] == "UTF-8 text with LF line endings"
    assert hashlib.sha256(lock.encode("utf-8")).hexdigest() == manifest["candidate_lock_sha256"]
    assert manifest["approval"] == "pending"
    for package in manifest["packages"]:
        assert metadata.version(package["name"]) == package["version"]
        expected = f"{package['name']}=={package['version']} --hash=sha256:{package['sha256']}"
        assert expected in lock.splitlines()
    for path, digest in manifest["project_input_sha256"].items():
        text = (root / path).read_text(encoding="utf-8")
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == digest

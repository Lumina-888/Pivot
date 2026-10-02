"""Public framework canaries only; no Pivot BudgetGate or Agent acceptance."""

import asyncio

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict


class Counter(TypedDict):
    count: int


@pytest.mark.parametrize("limit", [1, 2, 3])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_FR_AGENT_004_framework_resume_has_extra_execution_window(limit, asynchronous):
    builder = StateGraph(Counter)
    builder.add_node("tick", lambda state: {"count": state["count"] + 1})
    builder.add_edge(START, "tick")
    builder.add_edge("tick", "tick")
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "synthetic-counter"}, "recursion_limit": limit}

    async def run_async():
        with pytest.raises(GraphRecursionError):
            await graph.ainvoke({"count": 0}, config)
        first = await graph.aget_state(config)
        assert first.values["count"] == limit
        with pytest.raises(GraphRecursionError):
            await graph.ainvoke(None, config)
        resumed = await graph.aget_state(config)
        assert resumed.values["count"] - first.values["count"] == limit + 2

    if asynchronous:
        asyncio.run(run_async())
    else:
        with pytest.raises(GraphRecursionError):
            graph.invoke({"count": 0}, config)
        first = graph.get_state(config)
        assert first.values["count"] == limit
        with pytest.raises(GraphRecursionError):
            graph.invoke(None, config)
        assert graph.get_state(config).values["count"] - first.values["count"] == limit + 2


@pytest.mark.parametrize("asynchronous", [False, True])
def test_FR_AGENT_004_framework_command_reexecutes_prefix_without_committing_it(asynchronous):
    class Reply(TypedDict):
        reply: str
        consumed: int

    entered = []

    def ask(state):
        entered.append(state["consumed"])
        reply = interrupt({"kind": "synthetic-only"})
        return {"reply": reply, "consumed": state["consumed"] + 1}

    builder = StateGraph(Reply)
    builder.add_node("ask", ask)
    builder.add_edge(START, "ask")
    builder.add_edge("ask", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "synthetic-command"}, "recursion_limit": 3}

    async def run_async():
        paused = await graph.ainvoke({"reply": "", "consumed": 7}, config)
        assert paused["__interrupt__"]
        assert paused["consumed"] == 7
        resumed = await graph.ainvoke(Command(resume="fixture"), config)
        assert resumed["reply"] == "fixture"
        assert resumed["consumed"] == 8

    if asynchronous:
        asyncio.run(run_async())
    else:
        paused = graph.invoke({"reply": "", "consumed": 7}, config)
        assert paused["__interrupt__"]
        assert paused["consumed"] == 7
        resumed = graph.invoke(Command(resume="fixture"), config)
        assert resumed["reply"] == "fixture"
        assert resumed["consumed"] == 8
    # A returned State update counts one commit, but the prefix ran twice.
    assert entered == [7, 7]


def test_FR_AGENT_004_framework_superstep_is_not_a_node_or_provider_count():
    class Branches(TypedDict):
        left: int
        right: int

    entered = []

    def left(state):
        entered.append("left")
        return {"left": 1}

    def right(state):
        entered.append("right")
        return {"right": 1}

    builder = StateGraph(Branches)
    builder.add_node("left", left)
    builder.add_node("right", right)
    for node in ("left", "right"):
        builder.add_edge(START, node)
        builder.add_edge(node, END)
    graph = builder.compile()
    events = list(
        graph.stream(
            {"left": 0, "right": 0}, {"recursion_limit": 2}, stream_mode="debug"
        )
    )
    tasks = [event for event in events if event["type"] == "task"]
    assert {event["payload"]["name"] for event in tasks} == {"left", "right"}
    assert {event["step"] for event in tasks} == {1}
    assert sorted(entered) == ["left", "right"]
    # Debug output is measurement after execution, not a pre-dispatch safety gate.

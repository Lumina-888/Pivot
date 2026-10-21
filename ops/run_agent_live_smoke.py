"""ND-AGENT-05-B live smoke for the agent model channel.

Opt-in only: reads the S1 environment settings
(PIVOT_AGENT_MODEL_ENDPOINT / _MODEL / _API_KEY) and performs three
bounded, serial calls against the configured OpenAI-compatible
endpoint:

1. minimal chat completion (reachability, usage accounting);
2. forced native tool call (search_knowledge) — the model must emit
   one structured tool call whose arguments parse as JSON;
3. tool-result round trip — the step-2 assistant tool call and a
   synthetic tool result are fed back; the model must either issue
   the next tool call or produce a final text answer.

The script never prints the API key and stores nothing. It writes a
JSON report to stdout; exit code 0 means every assertion passed.
Credential custody stays with the caller's environment.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Callable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api", "src"))

from pivot.qa.agent_model import AgentModelSettings, get_tool_schemas

Transport = Callable[[dict[str, Any]], dict[str, Any]]

SYNTHETIC_TOOL_RESULT = json.dumps(
    {
        "hits": [
            {
                "chunk_id": "smoke-chunk-1",
                "text": "Synthetic smoke evidence: annual leave days depend on tenure.",
                "score": 0.9,
            }
        ]
    }
)


def tool_schemas() -> list[dict[str, Any]]:
    return get_tool_schemas()


def step_payloads(model: str) -> list[dict[str, Any]]:
    # Thinking mode rejects a forced tool_choice on the ADR-011 primary
    # model (provider returns HTTP 400), the same constraint class as
    # the 2026-10-06 Qwen probe. The smoke measures the tool protocol,
    # not reasoning, so every step runs with thinking disabled.
    thinking_off = {"thinking": {"type": "disabled"}}
    return [
        {
            "model": model,
            "messages": [
                {"role": "user", "content": "Reply with exactly one word: OK"}
            ],
            "max_tokens": 32,
            "temperature": 0,
            **thinking_off,
        },
        {
            "model": model,
            "messages": [
                {"role": "user", "content": "公司年假政策是怎样的？请检索知识库。"}
            ],
            "tools": tool_schemas(),
            "tool_choice": {
                "type": "function",
                "function": {"name": "search_knowledge"},
            },
            "max_tokens": 256,
            "temperature": 0,
            **thinking_off,
        },
    ]


def round_trip_payload(model: str, forced_response: dict[str, Any]) -> dict[str, Any]:
    assistant_message = forced_response["choices"][0]["message"]
    tool_call = assistant_message["tool_calls"][0]
    messages = [
        {"role": "user", "content": "公司年假政策是怎样的？请检索知识库。"},
        {
            "role": "assistant",
            "content": assistant_message.get("content"),
            "tool_calls": assistant_message["tool_calls"],
        },
        {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": SYNTHETIC_TOOL_RESULT,
        },
    ]
    return {
        "model": model,
        "messages": messages,
        "tools": tool_schemas(),
        "tool_choice": "auto",
        "max_tokens": 512,
        "temperature": 0,
        "thinking": {"type": "disabled"},
    }


def verify_chat(response: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    message = response.get("choices", [{}])[0].get("message", {})
    if not (message.get("content") or "").strip():
        failures.append("chat content is empty")
    usage = response.get("usage") or {}
    if not usage.get("total_tokens"):
        failures.append("chat usage missing total_tokens")
    return failures, {"content_preview": (message.get("content") or "")[:40]}


def verify_forced_tool(
    response: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    info: dict[str, Any] = {}
    message = response.get("choices", [{}])[0].get("message", {})
    tool_calls = message.get("tool_calls") or []
    if len(tool_calls) < 1:
        failures.append("forced call returned no tool_calls")
        return failures, info
    call = tool_calls[0]
    info["tool_call_id_present"] = bool(call.get("id"))
    if not call.get("id"):
        failures.append("tool call has no id")
    function = call.get("function", {})
    info["tool_name"] = function.get("name")
    if function.get("name") != "search_knowledge":
        failures.append(f"unexpected tool name: {function.get('name')}")
    try:
        arguments = json.loads(function.get("arguments") or "")
        info["arguments_keys"] = sorted(arguments.keys())
        if "query" not in arguments:
            failures.append("tool arguments missing query")
    except json.JSONDecodeError:
        failures.append("tool arguments are not valid JSON")
    return failures, info


def verify_round_trip(
    response: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    message = response.get("choices", [{}])[0].get("message", {})
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        branch = "next_tool_call"
        info = {"tool_name": tool_calls[0].get("function", {}).get("name")}
    elif (message.get("content") or "").strip():
        branch = "final_answer"
        info = {"content_preview": (message.get("content") or "")[:80]}
    else:
        branch = "empty"
        failures.append("round trip returned neither tool call nor text")
        info = {}
    usage = response.get("usage") or {}
    if not usage.get("total_tokens"):
        failures.append("round trip usage missing total_tokens")
    return failures, {"branch": branch, **info}


def run_smoke(model: str, transport: Transport) -> dict[str, Any]:
    report: dict[str, Any] = {"model": model, "steps": [], "total_tokens": 0}
    payloads = step_payloads(model)
    verifiers = [verify_chat, verify_forced_tool]
    forced_response: dict[str, Any] | None = None
    for index, payload in enumerate(payloads):
        name = ["chat", "forced_tool"][index]
        started = time.monotonic()
        try:
            response = transport(payload)
        except Exception as exc:  # record, never crash the smoke
            report["steps"].append(
                {"name": name, "failures": [f"transport_error: {exc}"], "info": {}}
            )
            report["passed"] = False
            return report
        latency_ms = round((time.monotonic() - started) * 1000)
        failures, info = verifiers[index](response)
        usage = response.get("usage") or {}
        report["total_tokens"] += usage.get("total_tokens") or 0
        report["steps"].append(
            {
                "name": name,
                "latency_ms": latency_ms,
                "usage": usage,
                "failures": failures,
                "info": info,
            }
        )
        if failures:
            report["passed"] = False
            return report
        if name == "forced_tool":
            forced_response = response
    assert forced_response is not None
    started = time.monotonic()
    try:
        response = transport(round_trip_payload(model, forced_response))
    except Exception as exc:  # record, never crash the smoke
        report["steps"].append(
            {
                "name": "tool_round_trip",
                "failures": [f"transport_error: {exc}"],
                "info": {},
            }
        )
        report["passed"] = False
        return report
    latency_ms = round((time.monotonic() - started) * 1000)
    failures, info = verify_round_trip(response)
    usage = response.get("usage") or {}
    report["total_tokens"] += usage.get("total_tokens") or 0
    report["steps"].append(
        {
            "name": "tool_round_trip",
            "latency_ms": latency_ms,
            "usage": usage,
            "failures": failures,
            "info": info,
        }
    )
    report["passed"] = not failures
    return report


def env_transport(settings: AgentModelSettings) -> Transport:
    endpoint = settings.primary.base_url.rstrip("/") + "/chat/completions"

    def call(payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                # The value is read from the caller's environment and
                # never printed or stored by this script.
                "Authorization": "Bearer " + settings.primary.api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {body[:400]}") from exc

    return call


def main() -> int:
    settings = AgentModelSettings.from_env(os.environ)
    report = run_smoke(settings.primary.model, env_transport(settings))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

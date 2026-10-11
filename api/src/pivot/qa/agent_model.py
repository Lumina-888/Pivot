"""Agent 模型适配器

封装真实 LLM 的调用，支持工具绑定和决策生成
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


class AgentModel:
    """Agent 决策模型适配器"""

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        """
        初始化模型

        Args:
            model_name: 模型名称
            temperature: 温度参数（0 = 确定性）
            api_key: API 密钥
            base_url: API 基础 URL
        """
        kwargs: dict[str, Any] = {
            "model": model_name,
            "temperature": temperature,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url

        self.model = ChatOpenAI(**kwargs)

    def decide(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AIMessage:
        """
        执行决策

        Args:
            messages: 历史消息（dict 格式）
            tools: 可用工具定义

        Returns:
            AIMessage（可能包含 tool_calls）
        """
        # 转换消息格式
        langchain_messages: list[BaseMessage] = []
        for msg in messages:
            role = msg.get("role") or msg.get("type")
            content = msg.get("content", "")

            if role in ("user", "human"):
                langchain_messages.append(HumanMessage(content=content))
            elif role in ("assistant", "ai"):
                langchain_messages.append(AIMessage(content=content))
            elif role == "system":
                langchain_messages.append(SystemMessage(content=content))
            else:
                # 跳过不识别的消息类型
                continue

        # 绑定工具
        model_with_tools = self.model.bind_tools(tools)

        # 调用模型
        response = model_with_tools.invoke(langchain_messages)

        # 确保返回的是 AIMessage
        if not isinstance(response, AIMessage):
            raise TypeError(f"Expected AIMessage, got {type(response)}")

        return response


def get_tool_schemas() -> list[dict[str, Any]]:
    """返回工具的 JSON Schema 定义"""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "description": "搜索知识库中的相关信息。用于查找文档、政策、规定等内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询词，应该简洁明确地描述需要查找的内容",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_evidence",
                "description": (
                    "读取已找到的证据详细内容。"
                    "必须先通过 search_knowledge 获得证据 ID。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "evidence_id": {
                            "type": "string",
                            "description": "证据 ID（从 search_knowledge 的结果中获得）",
                        }
                    },
                    "required": ["evidence_id"],
                },
            },
        },
    ]

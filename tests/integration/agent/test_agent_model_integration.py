"""Agent 模型集成测试

测试真实 LLM 的决策能力
"""

import os

import pytest
from pivot.qa.agent_model import AgentModel, get_tool_schemas


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="需要 OPENAI_API_KEY 环境变量",
)
class TestAgentModelIntegration:
    """Agent 模型集成测试（需要真实 API key）"""

    def test_model_decides_to_search_knowledge(self):
        """
        Given: 用户问了需要查知识库的问题
        When: 调用模型决策
        Then: 模型应该选择 search_knowledge 工具
        """
        model = AgentModel(model_name="gpt-4o-mini", temperature=0.0)

        messages = [
            {"role": "user", "content": "请问公司的考勤制度是什么？迟到三次怎么处理？"}
        ]

        response = model.decide(messages=messages, tools=get_tool_schemas())

        # 验证返回格式
        assert response.content is not None
        assert response.tool_calls is not None
        assert len(response.tool_calls) > 0

        # 验证工具选择
        tool_call = response.tool_calls[0]
        assert tool_call["name"] == "search_knowledge"
        assert "query" in tool_call["args"]
        assert len(tool_call["args"]["query"]) > 0

    def test_model_decides_to_answer_directly(self):
        """
        Given: 用户问了简单问候
        When: 调用模型决策
        Then: 模型应该直接回答，不调用工具
        """
        model = AgentModel(model_name="gpt-4o-mini", temperature=0.0)

        messages = [{"role": "user", "content": "你好"}]

        response = model.decide(messages=messages, tools=get_tool_schemas())

        # 验证返回格式
        assert response.content is not None

        # 简单问候应该直接回答，不调用工具
        assert response.tool_calls is None or len(response.tool_calls) == 0

    def test_model_handles_multi_turn_conversation(self):
        """
        Given: 多轮对话历史
        When: 调用模型决策
        Then: 模型应该正确处理上下文
        """
        model = AgentModel(model_name="gpt-4o-mini", temperature=0.0)

        messages = [
            {"role": "user", "content": "请查询考勤制度"},
            {
                "role": "assistant",
                "content": "我将为您查询考勤制度相关信息。",
            },
            {"role": "user", "content": "特别是迟到的规定"},
        ]

        response = model.decide(messages=messages, tools=get_tool_schemas())

        # 验证返回格式
        assert response.content is not None or response.tool_calls is not None

    def test_tool_schemas_are_valid(self):
        """
        Given: 工具定义
        When: 获取 schemas
        Then: 应该包含所有必需字段
        """
        schemas = get_tool_schemas()

        assert len(schemas) == 2

        # 验证 search_knowledge
        search_tool = schemas[0]
        assert search_tool["type"] == "function"
        assert search_tool["function"]["name"] == "search_knowledge"
        assert "description" in search_tool["function"]
        assert "parameters" in search_tool["function"]
        assert search_tool["function"]["parameters"]["type"] == "object"
        assert "query" in search_tool["function"]["parameters"]["properties"]

        # 验证 read_evidence
        read_tool = schemas[1]
        assert read_tool["type"] == "function"
        assert read_tool["function"]["name"] == "read_evidence"
        assert "description" in read_tool["function"]
        assert "parameters" in read_tool["function"]
        assert "evidence_id" in read_tool["function"]["parameters"]["properties"]

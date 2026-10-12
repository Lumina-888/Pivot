"""
ND-AGENT-02-F 单元测试：预算管理

测试覆盖：
- FR-AGENT-004: 执行前预算门禁
- 累计预算追踪
- 预算耗尽检测
- 未知用量 fail closed
"""

from __future__ import annotations

import pytest
from pivot.qa.agent_budget import (
    BudgetExhaustedError,
    BudgetGuard,
    BudgetPolicy,
    BudgetState,
)

# ====================
# BudgetPolicy 测试
# ====================


def test_budget_policy_validates_positive_limits():
    """
    Given: 创建 BudgetPolicy
    When: 参数为负数或零
    Then: 应该拒绝
    """
    with pytest.raises(ValueError, match="max_model_calls must be at least 1"):
        BudgetPolicy(
            max_model_calls=0,
            max_tool_calls=10,
            max_rewrite_count=2,
            timeout_seconds=60.0,
        )

    with pytest.raises(ValueError, match="max_tool_calls must be non-negative"):
        BudgetPolicy(
            max_model_calls=10,
            max_tool_calls=-1,
            max_rewrite_count=2,
            timeout_seconds=60.0,
        )

    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        BudgetPolicy(
            max_model_calls=10,
            max_tool_calls=20,
            max_rewrite_count=2,
            timeout_seconds=0.0,
        )


def test_budget_policy_accepts_valid_limits():
    """
    Given: 创建 BudgetPolicy
    When: 参数合法
    Then: 应该成功
    """
    policy = BudgetPolicy(
        max_model_calls=10,
        max_tool_calls=20,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )

    assert policy.max_model_calls == 10
    assert policy.max_tool_calls == 20
    assert policy.max_rewrite_count == 2
    assert policy.timeout_seconds == 60.0


# ====================
# BudgetState 测试
# ====================


def test_budget_state_tracks_consumption():
    """
    Given: BudgetState
    When: 消耗资源
    Then: 应该正确追踪
    """
    state = BudgetState()

    assert state.model_calls == 0
    assert state.tool_calls == 0
    assert state.rewrite_count == 0

    state.consume_model_call()
    state.consume_tool_call(2)
    state.consume_rewrite()

    assert state.model_calls == 1
    assert state.tool_calls == 2
    assert state.rewrite_count == 1


def test_budget_state_calculates_remaining():
    """
    Given: BudgetState 已消耗部分资源
    When: 查询剩余预算
    Then: 应该返回正确值
    """
    policy = BudgetPolicy(
        max_model_calls=10,
        max_tool_calls=20,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )
    state = BudgetState(model_calls=3, tool_calls=5, rewrite_count=1)

    assert state.remaining_model_calls(policy) == 7
    assert state.remaining_tool_calls(policy) == 15
    assert state.remaining_rewrites(policy) == 1


def test_budget_state_remaining_never_negative():
    """
    Given: BudgetState 超出限制（异常情况）
    When: 查询剩余预算
    Then: 应该返回 0 而不是负数
    """
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )
    state = BudgetState(model_calls=10, tool_calls=20, rewrite_count=5)

    assert state.remaining_model_calls(policy) == 0
    assert state.remaining_tool_calls(policy) == 0
    assert state.remaining_rewrites(policy) == 0


def test_budget_state_detects_exhaustion():
    """
    Given: BudgetState
    When: 任一维度耗尽
    Then: is_exhausted 应该返回 True
    """
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )

    # 模型调用耗尽
    state1 = BudgetState(model_calls=5)
    assert state1.is_exhausted(policy) is True

    # 工具调用耗尽
    state2 = BudgetState(tool_calls=10)
    assert state2.is_exhausted(policy) is True

    # 改写耗尽
    state3 = BudgetState(rewrite_count=2)
    assert state3.is_exhausted(policy) is True

    # 超时
    state4 = BudgetState(elapsed_seconds=60.0)
    assert state4.is_exhausted(policy) is True

    # 未耗尽
    state5 = BudgetState(model_calls=3, tool_calls=5, rewrite_count=1, elapsed_seconds=30.0)
    assert state5.is_exhausted(policy) is False


def test_budget_state_check_can_call_model():
    """
    Given: BudgetState
    When: 检查是否可以调用模型
    Then: 预算不足时应该抛出异常
    """
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )

    # 预算充足
    state = BudgetState(model_calls=3)
    state.check_can_call_model(policy)  # 不抛异常

    # 预算耗尽
    state_exhausted = BudgetState(model_calls=5)
    with pytest.raises(BudgetExhaustedError, match="Model call budget exhausted"):
        state_exhausted.check_can_call_model(policy)


def test_budget_state_check_can_call_tool():
    """
    Given: BudgetState
    When: 检查是否可以调用工具
    Then: 预算不足时应该抛出异常
    """
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )

    # 预算充足
    state = BudgetState(tool_calls=8)
    state.check_can_call_tool(policy, count=1)  # 不抛异常

    # 单次调用超出
    with pytest.raises(BudgetExhaustedError, match="Tool call budget exhausted"):
        state.check_can_call_tool(policy, count=3)

    # 多次调用累计超出
    state2 = BudgetState(tool_calls=10)
    with pytest.raises(BudgetExhaustedError):
        state2.check_can_call_tool(policy, count=1)


def test_budget_state_check_can_rewrite():
    """
    Given: BudgetState
    When: 检查是否可以改写查询
    Then: 预算不足时应该抛出异常
    """
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )

    # 预算充足
    state = BudgetState(rewrite_count=1)
    state.check_can_rewrite(policy)  # 不抛异常

    # 预算耗尽
    state_exhausted = BudgetState(rewrite_count=2)
    with pytest.raises(BudgetExhaustedError, match="Rewrite budget exhausted"):
        state_exhausted.check_can_rewrite(policy)


# ====================
# BudgetGuard 测试
# ====================


def test_budget_guard_before_model_call_checks_budget():
    """
    Given: BudgetGuard
    When: 模型调用前检查
    Then: 预算不足时应该阻止
    """
    policy = BudgetPolicy(
        max_model_calls=3,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )
    state = BudgetState(model_calls=3)
    guard = BudgetGuard(policy, state)

    with pytest.raises(BudgetExhaustedError):
        guard.before_model_call()


def test_budget_guard_after_model_call_updates_state():
    """
    Given: BudgetGuard
    When: 模型调用后更新
    Then: 应该增加计数
    """
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )
    state = BudgetState()
    guard = BudgetGuard(policy, state)

    assert state.model_calls == 0
    guard.after_model_call()
    assert state.model_calls == 1


def test_budget_guard_before_tool_calls_checks_batch():
    """
    Given: BudgetGuard
    When: 工具调用前检查多个工具
    Then: 应该检查总数是否超出
    """
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )
    state = BudgetState(tool_calls=8)
    guard = BudgetGuard(policy, state)

    # 3 个工具调用会超出预算
    tool_calls = [
        {"id": "call_1", "name": "search_knowledge", "args": {"query": "test"}},
        {"id": "call_2", "name": "read_evidence", "args": {"evidence_id": "ev_1"}},
        {"id": "call_3", "name": "search_knowledge", "args": {"query": "test2"}},
    ]

    with pytest.raises(BudgetExhaustedError):
        guard.before_tool_calls(tool_calls)


def test_budget_guard_after_tool_calls_updates_batch():
    """
    Given: BudgetGuard
    When: 工具调用后更新
    Then: 应该按实际调用数量增加
    """
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )
    state = BudgetState()
    guard = BudgetGuard(policy, state)

    tool_calls = [
        {"id": "call_1", "name": "search_knowledge", "args": {"query": "test"}},
        {"id": "call_2", "name": "read_evidence", "args": {"evidence_id": "ev_1"}},
    ]

    assert state.tool_calls == 0
    guard.after_tool_calls(tool_calls)
    assert state.tool_calls == 2


def test_budget_guard_repeated_query_consumes_budget():
    """
    Given: BudgetGuard
    When: 重复相同查询
    Then: 每次都应该消耗预算
    
    验证 FR-AGENT-004: 重复 query 仍消耗调用预算
    """
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=5,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )
    state = BudgetState()
    guard = BudgetGuard(policy, state)

    # 第一次查询
    guard.before_tool_calls([{"id": "call_1", "name": "search_knowledge", "args": {"query": "考勤"}}])
    guard.after_tool_calls([{"id": "call_1", "name": "search_knowledge", "args": {"query": "考勤"}}])
    assert state.tool_calls == 1

    # 重复相同查询，仍然消耗预算
    guard.before_tool_calls([{"id": "call_2", "name": "search_knowledge", "args": {"query": "考勤"}}])
    guard.after_tool_calls([{"id": "call_2", "name": "search_knowledge", "args": {"query": "考勤"}}])
    assert state.tool_calls == 2


def test_budget_guard_rewrite_limit_enforced():
    """
    Given: BudgetGuard with max_rewrite_count=2
    When: 尝试第 3 次改写
    Then: 应该拒绝
    
    验证 FR-AGENT-004: rewrite≤2
    """
    policy = BudgetPolicy(
        max_model_calls=10,
        max_tool_calls=20,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )
    state = BudgetState()
    guard = BudgetGuard(policy, state)

    # 第一次改写
    guard.before_rewrite()
    guard.after_rewrite()
    assert state.rewrite_count == 1

    # 第二次改写
    guard.before_rewrite()
    guard.after_rewrite()
    assert state.rewrite_count == 2

    # 第三次改写应该被拒绝
    with pytest.raises(BudgetExhaustedError):
        guard.before_rewrite()


def test_budget_guard_get_summary():
    """
    Given: BudgetGuard
    When: 获取预算摘要
    Then: 应该返回完整信息
    """
    policy = BudgetPolicy(
        max_model_calls=10,
        max_tool_calls=20,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )
    state = BudgetState(model_calls=3, tool_calls=5, rewrite_count=1, elapsed_seconds=15.0)
    guard = BudgetGuard(policy, state)

    summary = guard.get_summary()

    assert summary["model_calls"]["used"] == 3
    assert summary["model_calls"]["limit"] == 10
    assert summary["model_calls"]["remaining"] == 7

    assert summary["tool_calls"]["used"] == 5
    assert summary["tool_calls"]["limit"] == 20
    assert summary["tool_calls"]["remaining"] == 15

    assert summary["rewrites"]["used"] == 1
    assert summary["rewrites"]["limit"] == 2
    assert summary["rewrites"]["remaining"] == 1

    assert summary["elapsed_seconds"] == 15.0
    assert summary["timeout_seconds"] == 60.0
    assert summary["exhausted"] is False


def test_budget_guard_is_exhausted():
    """
    Given: BudgetGuard
    When: 预算耗尽
    Then: is_exhausted 应该返回 True
    """
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
    )

    # 未耗尽
    state1 = BudgetState(model_calls=3)
    guard1 = BudgetGuard(policy, state1)
    assert guard1.is_exhausted() is False

    # 耗尽
    state2 = BudgetState(model_calls=5)
    guard2 = BudgetGuard(policy, state2)
    assert guard2.is_exhausted() is True


def test_budget_reserves_cost_and_tokens_before_call():
    """费用和 token 在调用前预扣，返回后按实际值结算。"""
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
        max_cost_usd=1.0,
        max_total_tokens=100,
    )
    guard = BudgetGuard(policy, BudgetState())

    guard.before_model_call(estimated_cost_usd=0.4, estimated_tokens=30)
    assert guard.state.reserved_cost_usd == 0.4
    assert guard.state.reserved_tokens == 30

    guard.settle_model_call(actual_cost_usd=0.25, actual_tokens=20)
    assert guard.state.cost_usd == 0.25
    assert guard.state.total_tokens == 20
    assert guard.state.reserved_cost_usd == 0.0
    assert guard.state.reserved_tokens == 0
    assert guard.state.model_calls == 1


def test_budget_rejects_call_when_estimate_exceeds_remaining():
    """预估超过剩余额度时拒绝，并且不增加已消耗。"""
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
        max_cost_usd=1.0,
        max_total_tokens=100,
    )
    state = BudgetState(cost_usd=0.8, total_tokens=90)
    guard = BudgetGuard(policy, state)

    with pytest.raises(BudgetExhaustedError):
        guard.before_model_call(estimated_cost_usd=0.3, estimated_tokens=5)
    with pytest.raises(BudgetExhaustedError):
        guard.before_model_call(estimated_cost_usd=0.1, estimated_tokens=20)

    assert state.model_calls == 0
    assert state.reserved_cost_usd == 0.0
    assert state.reserved_tokens == 0


def test_budget_unknown_usage_fails_closed_without_recording_zero():
    """未知用量不能记零，也不能继续下一次调用。"""
    policy = BudgetPolicy(
        max_model_calls=5,
        max_tool_calls=10,
        max_rewrite_count=2,
        timeout_seconds=60.0,
        max_cost_usd=1.0,
        max_total_tokens=100,
    )
    guard = BudgetGuard(policy, BudgetState())
    guard.before_model_call(estimated_cost_usd=0.1, estimated_tokens=10)

    with pytest.raises(BudgetExhaustedError, match="unknown usage"):
        guard.settle_model_call(actual_cost_usd=None, actual_tokens=None)

    assert guard.state.cost_usd == 0.0
    assert guard.state.total_tokens == 0
    assert guard.state.unknown_usage is True
    with pytest.raises(BudgetExhaustedError):
        guard.before_model_call(estimated_cost_usd=0.1, estimated_tokens=10)


def test_budget_missing_policy_fails_closed():
    """
    Given: 创建 BudgetPolicy
    When: 缺少必需策略参数
    Then: 应该 fail closed
    
    验证 FR-AGENT-004: 无必需策略时 fail closed
    """
    # max_model_calls 必须至少为 1
    with pytest.raises(ValueError):
        BudgetPolicy(
            max_model_calls=0,
            max_tool_calls=10,
            max_rewrite_count=2,
            timeout_seconds=60.0,
        )

    # timeout 必须为正数
    with pytest.raises(ValueError):
        BudgetPolicy(
            max_model_calls=5,
            max_tool_calls=10,
            max_rewrite_count=2,
            timeout_seconds=-1.0,
        )

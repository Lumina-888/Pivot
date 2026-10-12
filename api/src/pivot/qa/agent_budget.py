"""
Agent 预算管理实现

实现 FR-AGENT-004：执行前预算门禁
- 累计预算追踪（模型调用、工具调用、查询改写）
- 执行前预扣，未知用量 fail closed
- 独立图门禁，不依赖 recursion_limit
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class BudgetPolicy:
    """
    预算策略

    定义 Agent 执行的资源限制
    """

    max_model_calls: int
    max_tool_calls: int
    max_rewrite_count: int
    timeout_seconds: float
    max_cost_usd: float | None = None
    max_total_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.max_model_calls < 1:
            raise ValueError("max_model_calls must be at least 1")
        if self.max_tool_calls < 0:
            raise ValueError("max_tool_calls must be non-negative")
        if self.max_rewrite_count < 0:
            raise ValueError("max_rewrite_count must be non-negative")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be non-negative")
        if self.max_total_tokens is not None and self.max_total_tokens < 0:
            raise ValueError("max_total_tokens must be non-negative")


@dataclass
class BudgetState:
    """
    预算状态

    追踪当前执行的资源消耗
    """

    model_calls: int = 0
    tool_calls: int = 0
    rewrite_count: int = 0
    elapsed_seconds: float = 0.0
    cost_usd: float = 0.0
    total_tokens: int = 0
    reserved_cost_usd: float = 0.0
    reserved_tokens: int = 0
    unknown_usage: bool = False

    def remaining_model_calls(self, policy: BudgetPolicy) -> int:
        """剩余模型调用次数"""
        return max(0, policy.max_model_calls - self.model_calls)

    def remaining_tool_calls(self, policy: BudgetPolicy) -> int:
        """剩余工具调用次数"""
        return max(0, policy.max_tool_calls - self.tool_calls)

    def remaining_rewrites(self, policy: BudgetPolicy) -> int:
        """剩余改写次数"""
        return max(0, policy.max_rewrite_count - self.rewrite_count)

    def is_exhausted(self, policy: BudgetPolicy) -> bool:
        """预算是否耗尽"""
        return (
            self.model_calls >= policy.max_model_calls
            or self.tool_calls >= policy.max_tool_calls
            or self.rewrite_count >= policy.max_rewrite_count
            or self.elapsed_seconds >= policy.timeout_seconds
            or self.unknown_usage
            or (
                policy.max_cost_usd is not None
                and self.cost_usd + self.reserved_cost_usd >= policy.max_cost_usd
            )
            or (
                policy.max_total_tokens is not None
                and self.total_tokens + self.reserved_tokens >= policy.max_total_tokens
            )
        )

    def check_can_call_model(self, policy: BudgetPolicy) -> None:
        """
        检查是否可以调用模型

        Raises:
            BudgetExhaustedError: 预算不足
        """
        if self.model_calls >= policy.max_model_calls:
            raise BudgetExhaustedError(
                f"Model call budget exhausted: {self.model_calls}/{policy.max_model_calls}"
            )

    def check_can_call_tool(self, policy: BudgetPolicy, count: int = 1) -> None:
        """
        检查是否可以调用工具

        Args:
            policy: 预算策略
            count: 要调用的工具数量

        Raises:
            BudgetExhaustedError: 预算不足
        """
        if self.tool_calls + count > policy.max_tool_calls:
            raise BudgetExhaustedError(
                f"Tool call budget exhausted: {self.tool_calls + count} > {policy.max_tool_calls}"
            )

    def check_can_rewrite(self, policy: BudgetPolicy) -> None:
        """
        检查是否可以改写查询

        Raises:
            BudgetExhaustedError: 预算不足
        """
        if self.rewrite_count >= policy.max_rewrite_count:
            raise BudgetExhaustedError(
                f"Rewrite budget exhausted: {self.rewrite_count}/{policy.max_rewrite_count}"
            )

    def consume_model_call(self) -> None:
        """消耗一次模型调用"""
        self.model_calls += 1

    def consume_tool_call(self, count: int = 1) -> None:
        """消耗工具调用"""
        self.tool_calls += count

    def consume_rewrite(self) -> None:
        """消耗一次查询改写"""
        self.rewrite_count += 1

    def update_elapsed(self, seconds: float) -> None:
        """更新已用时间"""
        self.elapsed_seconds = seconds


class BudgetModel(Protocol):
    def decide(self) -> Any: ...


class BudgetExhaustedError(Exception):
    """预算耗尽错误"""

    pass


class BudgetGuard:
    """
    预算守卫

    在执行前检查预算，执行后更新状态
    """

    def __init__(self, policy: BudgetPolicy, state: BudgetState) -> None:
        self.policy = policy
        self.state = state

    def before_model_call(
        self,
        *,
        estimated_cost_usd: float = 0.0,
        estimated_tokens: int = 0,
    ) -> None:
        """
        模型调用前检查并预扣费用与 token。

        Raises:
            BudgetExhaustedError: 预算不足
        """
        if estimated_cost_usd < 0 or estimated_tokens < 0:
            raise ValueError("estimate must be non-negative")
        self.state.check_can_call_model(self.policy)
        if self.state.unknown_usage:
            raise BudgetExhaustedError("unknown usage blocks further calls")
        if (
            self.policy.max_cost_usd is not None
            and self.state.cost_usd + self.state.reserved_cost_usd + estimated_cost_usd
            > self.policy.max_cost_usd
        ):
            raise BudgetExhaustedError("cost budget exhausted")
        if (
            self.policy.max_total_tokens is not None
            and self.state.total_tokens + self.state.reserved_tokens + estimated_tokens
            > self.policy.max_total_tokens
        ):
            raise BudgetExhaustedError("token budget exhausted")
        self.state.reserved_cost_usd += estimated_cost_usd
        self.state.reserved_tokens += estimated_tokens

    def after_model_call(self) -> None:
        """模型调用后更新"""
        self.state.consume_model_call()

    def settle_reported_usage(self, usage: dict[str, Any] | None) -> None:
        """结算模型返回的 token 用量；缺失时不记零。"""
        if not isinstance(usage, dict):
            self.settle_model_call(actual_cost_usd=None, actual_tokens=None)
            return
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if (
            type(input_tokens) is not int
            or type(output_tokens) is not int
            or input_tokens < 0
            or output_tokens < 0
        ):
            self.settle_model_call(actual_cost_usd=None, actual_tokens=None)
            return
        self.settle_model_call(
            actual_cost_usd=0.0,
            actual_tokens=input_tokens + output_tokens,
        )

    def settle_model_call(
        self,
        *,
        actual_cost_usd: float | None,
        actual_tokens: int | None,
    ) -> None:
        """按实际用量结算；未知用量不记零并关闭后续调用。"""
        self.state.reserved_cost_usd = 0.0
        self.state.reserved_tokens = 0
        self.state.consume_model_call()
        if actual_cost_usd is None or actual_tokens is None:
            self.state.unknown_usage = True
            raise BudgetExhaustedError("unknown usage")
        if actual_cost_usd < 0 or actual_tokens < 0:
            raise ValueError("actual usage must be non-negative")
        self.state.cost_usd += actual_cost_usd
        self.state.total_tokens += actual_tokens

    def call_with_fallback(
        self,
        primary: BudgetModel,
        fallback: BudgetModel,
        *,
        retryable: frozenset[str],
        estimated_cost_usd: float = 0.1,
        estimated_tokens: int = 10,
    ) -> Any:
        """主备调用共享同一账本；只有可重试失败才切换。"""
        self.before_model_call(
            estimated_cost_usd=estimated_cost_usd,
            estimated_tokens=estimated_tokens,
        )
        try:
            result = primary.decide()
        except Exception as exc:
            self.settle_model_call(
                actual_cost_usd=estimated_cost_usd,
                actual_tokens=estimated_tokens,
            )
            if str(exc) not in retryable:
                raise
            self.before_model_call(
                estimated_cost_usd=estimated_cost_usd,
                estimated_tokens=estimated_tokens,
            )
            result = fallback.decide()
        self.settle_model_call(
            actual_cost_usd=estimated_cost_usd,
            actual_tokens=estimated_tokens,
        )
        return result

    def before_tool_calls(self, tool_calls: list[dict[str, Any]]) -> None:
        """
        工具调用前检查

        Args:
            tool_calls: 工具调用列表

        Raises:
            BudgetExhaustedError: 预算不足
        """
        count = len(tool_calls)
        self.state.check_can_call_tool(self.policy, count)

    def after_tool_calls(self, tool_calls: list[dict[str, Any]]) -> None:
        """工具调用后更新"""
        count = len(tool_calls)
        self.state.consume_tool_call(count)

    def before_rewrite(self) -> None:
        """
        查询改写前检查

        Raises:
            BudgetExhaustedError: 预算不足
        """
        self.state.check_can_rewrite(self.policy)

    def after_rewrite(self) -> None:
        """查询改写后更新"""
        self.state.consume_rewrite()

    def is_exhausted(self) -> bool:
        """检查预算是否耗尽"""
        return self.state.is_exhausted(self.policy)

    def state_snapshot(self) -> dict[str, Any]:
        """恢复所需的累计账本，不含策略或供应商信息。"""
        return {
            "model_calls": self.state.model_calls,
            "tool_calls": self.state.tool_calls,
            "rewrite_count": self.state.rewrite_count,
            "elapsed_seconds": self.state.elapsed_seconds,
            "cost_usd": self.state.cost_usd,
            "total_tokens": self.state.total_tokens,
            "reserved_cost_usd": self.state.reserved_cost_usd,
            "reserved_tokens": self.state.reserved_tokens,
            "unknown_usage": self.state.unknown_usage,
        }

    def get_summary(self) -> dict[str, Any]:
        """获取预算使用摘要"""
        return {
            "model_calls": {
                "used": self.state.model_calls,
                "limit": self.policy.max_model_calls,
                "remaining": self.state.remaining_model_calls(self.policy),
            },
            "tool_calls": {
                "used": self.state.tool_calls,
                "limit": self.policy.max_tool_calls,
                "remaining": self.state.remaining_tool_calls(self.policy),
            },
            "rewrites": {
                "used": self.state.rewrite_count,
                "limit": self.policy.max_rewrite_count,
                "remaining": self.state.remaining_rewrites(self.policy),
            },
            "elapsed_seconds": self.state.elapsed_seconds,
            "timeout_seconds": self.policy.timeout_seconds,
            "exhausted": self.is_exhausted(),
        }

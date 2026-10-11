"""Writer failures use SPEC appendix B.1 codes. Messages never include secrets."""

from __future__ import annotations


class WriterError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AnswerNotPublishedError(Exception):
    """Answer did not pass verification gate."""

    pass


class AgentToolError(Exception):
    """Agent 工具执行错误（参数错误、权限错误等）"""

    pass


class UnknownToolError(Exception):
    """工具不在白名单中"""

    pass

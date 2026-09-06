"""Actors and recording ports owned by M06. Callers supply persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Actor:
    user_id: str
    username: str
    role: str
    status: str = "active"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class Clock(Protocol):
    def now(self) -> datetime: ...

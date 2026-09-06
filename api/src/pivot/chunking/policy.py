"""Injectable chunking policy. Token window remains TBD-P0."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingPolicy:
    max_chars: int
    overlap_chars: int

    def __post_init__(self) -> None:
        if self.max_chars <= 0 or self.overlap_chars < 0 or self.overlap_chars >= self.max_chars:
            raise ValueError("invalid chunking policy")

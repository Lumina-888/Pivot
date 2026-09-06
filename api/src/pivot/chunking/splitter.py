"""Split parsed blocks into chunks with locators (SPEC §6.2)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pivot.chunking.policy import ChunkingPolicy
from pivot.parsing.models import ParsedBlock


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    text_hash: str
    locator: str
    title_path: str
    raw_char_start: int
    raw_char_end: int


class ChunkSplitter:
    def __init__(self, policy: ChunkingPolicy) -> None:
        self._policy = policy

    def split(self, blocks: tuple[ParsedBlock, ...]) -> tuple[ChunkDraft, ...]:
        drafts: list[ChunkDraft] = []
        cursor = 0
        for block in blocks:
            text = block.text.strip()
            if not text:
                continue
            start = 0
            while start < len(text):
                end = min(len(text), start + self._policy.max_chars)
                piece = text[start:end]
                digest = hashlib.sha256(piece.encode("utf-8")).hexdigest()
                drafts.append(
                    ChunkDraft(
                        text=piece,
                        text_hash=digest,
                        locator=block.locator,
                        title_path=block.title_path,
                        raw_char_start=cursor + start,
                        raw_char_end=cursor + end,
                    )
                )
                if end >= len(text):
                    break
                start = end - self._policy.overlap_chars
            cursor += len(text)
        return tuple(drafts)

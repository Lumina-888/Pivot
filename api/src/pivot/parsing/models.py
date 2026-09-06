"""Parsed document blocks produced by pluggable parsers (SPEC §6.1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    locator: str
    title_path: str = ""


@dataclass(frozen=True)
class ParsedDocument:
    kind: str
    blocks: tuple[ParsedBlock, ...]

    @property
    def text(self) -> str:
        return "\n".join(block.text for block in self.blocks if block.text.strip())

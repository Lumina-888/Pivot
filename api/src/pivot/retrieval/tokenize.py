"""Injected lexical tokenizer. Not jieba; Chinese segmentation stays TBD-P0."""

from __future__ import annotations

from typing import Protocol


class Tokenizer(Protocol):
    def tokenize(self, text: str) -> tuple[str, ...]: ...


class SimpleLexTokenizer:
    """CJK unigrams plus latin/digit words. Not a frozen production analyzer."""

    def tokenize(self, text: str) -> tuple[str, ...]:
        tokens: list[str] = []
        buf: list[str] = []
        for char in text.lower():
            if ("a" <= char <= "z") or ("0" <= char <= "9"):
                buf.append(char)
                continue
            if buf:
                tokens.append("".join(buf))
                buf = []
            if "\u4e00" <= char <= "\u9fff":
                tokens.append(char)
        if buf:
            tokens.append("".join(buf))
        return tuple(tokens)

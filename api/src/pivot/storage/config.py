"""Injected storage configuration; no infrastructure endpoints are hard-coded."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ObjectStoreConfig:
    endpoint: str
    bucket: str


@dataclass(frozen=True, slots=True)
class VectorStoreConfig:
    endpoint: str
    collection: str


@dataclass(frozen=True, slots=True)
class QueueStoreConfig:
    endpoint: str
    queue_name: str


@dataclass(frozen=True, slots=True)
class CacheStoreConfig:
    endpoint: str
    key_prefix: str = "pivot:"

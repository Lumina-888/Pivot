from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pivot.chunking import ChunkingPolicy, ChunkSplitter
from pivot_worker.ingest import IngestWorker, RecordingSink

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))


@pytest.fixture
def sink() -> RecordingSink:
    return RecordingSink()


@pytest.fixture
def worker(sink: RecordingSink) -> IngestWorker:
    return IngestWorker(
        sink=sink,
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
        dimension=8,
    )

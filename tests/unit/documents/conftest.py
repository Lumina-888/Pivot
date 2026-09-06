from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pivot.documents.service import DocumentService

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from fakes import (  # noqa: E402
    MemoryAudits,
    MemoryChunks,
    MemoryDocuments,
    MemoryObjects,
    MemoryTasks,
    MemoryVersions,
)


@pytest.fixture
def service() -> DocumentService:
    return DocumentService(
        documents=MemoryDocuments(),
        versions=MemoryVersions(),
        chunks=MemoryChunks(),
        tasks=MemoryTasks(),
        objects=MemoryObjects(),
        audits=MemoryAudits(),
    )

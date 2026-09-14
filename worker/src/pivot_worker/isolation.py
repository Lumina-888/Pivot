"""Worker isolation: restricted temp workspace.

Local parsers stay offline; MinerU uses injected HTTP.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory


@contextmanager
def isolated_workspace() -> Iterator[Path]:
    with TemporaryDirectory(prefix="pivot-worker-") as folder:
        yield Path(folder)

from __future__ import annotations

from pathlib import Path

_MAIN = Path(__file__).resolve().parents[3] / "worker" / "src" / "pivot_worker" / "__main__.py"


def test_NFR_OBS_worker_process_starts_celery():
    text = _MAIN.read_text(encoding="utf-8")
    assert "start_celery_worker" in text
    assert "start_health_server" in text
    assert "while True" not in text

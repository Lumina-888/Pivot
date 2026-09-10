from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_ATTEMPTS = _ROOT / "api" / "src" / "pivot" / "auth" / "attempts.py"
_SETTINGS = _ROOT / "api" / "src" / "pivot" / "http" / "settings.py"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "login-rate-limit.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


def test_FR_AUTH_002_login_rate_source_does_not_freeze_tbd_threshold():
    attempts = _ATTEMPTS.read_text(encoding="utf-8")
    settings = _SETTINGS.read_text(encoding="utf-8")
    combined = f"{attempts}\n{settings}"
    assert "PIVOT_LOGIN_MAX_FAILURES" in settings
    assert "PIVOT_LOGIN_WINDOW_SECONDS" in settings
    assert "max_failures: int" in attempts or "max_failures:" in attempts
    assert "window_seconds" in attempts
    for frozen in ("max_failures=5", "max_failures = 5", "LOGIN_MAX_FAILURES = 5"):
        assert frozen not in combined
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "TBD-P0" in evidence


def test_GATE_P0_005_not_verified_by_login_rate_limit():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-005" in evidence
    assert "unverified" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-005" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")

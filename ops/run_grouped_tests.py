#!/usr/bin/env python3
"""Run Wave 1/2 checks in isolated pytest groups (fakes.py name collision).

This is an M11 harness. It does not start Compose, uvicorn, Celery, or mark GATE-P0 verified.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "api" / "src"
WORKER_SRC = ROOT / "worker" / "src"

GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("M01-auth", ("tests/unit/auth", "tests/security/auth")),
    ("M02-documents", ("tests/unit/documents",)),
    ("M04-retrieval", ("tests/unit/retrieval", "tests/security/retrieval")),
    ("M05-qa-stream", ("tests/unit/qa", "tests/unit/runs", "tests/contract/stream")),
    ("M06-export-audit", ("tests/unit/exports", "tests/unit/audit", "tests/security/export")),
    ("M07-worker", ("tests/unit/worker",)),
    (
        "M00-M03-contract-db",
        ("tests/integration/db", "tests/contract", "--ignore=tests/contract/stream"),
    ),
    ("M11-pipeline", ("tests/integration/pipeline",)),
    ("M11-security-ops", ("tests/security/ops",)),
    ("M11-performance-plan", ("tests/performance",)),
)


def run(command: list[str], env: dict[str, str], cwd: Path | None = None) -> int:
    print("+", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=cwd or ROOT, env=env, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-web", action="store_true")
    parser.add_argument("--skip-ruff", action="store_true")
    args = parser.parse_args()

    env = os.environ.copy()
    pythonpath = os.pathsep.join([str(API_SRC), str(WORKER_SRC), env.get("PYTHONPATH", "")]).strip(
        os.pathsep
    )
    env["PYTHONPATH"] = pythonpath
    failures: list[str] = []

    for name, parts in GROUPS:
        command = [sys.executable, "-m", "pytest", "-q", *parts]
        if run(command, env) != 0:
            failures.append(name)

    if not args.skip_ruff:
        ruff = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--config",
            str(ROOT / "api" / "pyproject.toml"),
            "api/src",
            "worker/src",
            "tests/integration/pipeline",
            "tests/security/ops",
            "tests/performance",
            "ops",
        ]
        if run(ruff, env) != 0:
            failures.append("ruff")
        compileall = [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "api/src",
            "worker/src",
            "tests/integration/pipeline",
        ]
        if run(compileall, env) != 0:
            failures.append("compileall")

    if not args.skip_web:
        npm = "npm.cmd" if os.name == "nt" else "npm"
        npx = "npx.cmd" if os.name == "nt" else "npx"
        web = ROOT / "web"
        if run([npm, "--prefix", "web", "ci"], env) != 0:
            failures.append("web-ci")
        else:
            web_checks: tuple[tuple[str, list[str], Path], ...] = (
                ("web-test", [npm, "--prefix", "web", "test"], ROOT),
                (
                    "web-user-e2e",
                    [npx, "tsx", "../tests/e2e/user/test_user_web.mjs"],
                    web,
                ),
                (
                    "web-admin-e2e",
                    [npx, "tsx", "../tests/e2e/admin/test_admin_web.mjs"],
                    web,
                ),
                ("web-typecheck", [npm, "--prefix", "web", "run", "typecheck"], ROOT),
                ("web-lint", [npm, "--prefix", "web", "run", "lint"], ROOT),
            )
            for name, command, cwd in web_checks:
                if run(command, env, cwd=cwd) != 0:
                    failures.append(name)

    if failures:
        print("failed groups:", ", ".join(failures), file=sys.stderr)
        return 1
    print("grouped checks passed (not GATE-P0 verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

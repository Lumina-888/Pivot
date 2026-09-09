"""Local uvicorn + Next stack for opt-in Playwright login. Not a production runtime."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_API_SRC = _ROOT / "api" / "src"
_WEB = _ROOT / "web"
_USERNAME = "admin"
_PASSWORD = "playwright-admin-password"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_http(url: str, timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    last_error = "timeout"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if 200 <= response.status < 500:
                    return
                last_error = f"status {response.status}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.25)
    raise RuntimeError(f"timed out waiting for {url}: {last_error}")


def _stop(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@dataclass
class BrowserStack:
    page: Any
    web_origin: str
    username: str
    password: str
    _browser: Any
    _playwright: Any
    _api: subprocess.Popen[str]
    _web: subprocess.Popen[str]

    def close(self) -> None:
        try:
            self._browser.close()
        finally:
            try:
                self._playwright.stop()
            finally:
                _stop(self._web)
                _stop(self._api)


def start_browser_stack() -> BrowserStack:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed; pip install -e ./api[playwright] "
            "&& playwright install chromium"
        ) from exc

    api_port = _free_port()
    web_port = _free_port()
    api_origin = f"http://127.0.0.1:{api_port}"
    web_origin = f"http://127.0.0.1:{web_port}"
    api_env = os.environ.copy()
    api_env["PYTHONPATH"] = os.pathsep.join(
        [str(_API_SRC), api_env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    api_env.update(
        {
            "PIVOT_STORAGE": "memory",
            "PIVOT_TOKEN_SECRET": "playwright-test-secret",
            "PIVOT_ACCESS_TTL": "60",
            "PIVOT_REFRESH_TTL": "3600",
            "PIVOT_EXPORT_TTL": "3600",
            "PIVOT_DOWNLOAD_TTL": "300",
            "PIVOT_EXPORT_PUBLIC_BASE": "https://files.pivot.test",
            "PIVOT_RETRIEVAL_K": "4",
            "PIVOT_BOOTSTRAP_USERNAME": _USERNAME,
            "PIVOT_BOOTSTRAP_PASSWORD": _PASSWORD,
            "PIVOT_ARGON2_TIME_COST": "1",
            "PIVOT_ARGON2_MEMORY_COST": "8",
            "PIVOT_ARGON2_PARALLELISM": "1",
        }
    )
    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "pivot.http.main:app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=_ROOT,
        env=api_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    web_env = os.environ.copy()
    web_env["PIVOT_API_ORIGIN"] = api_origin
    web_env["NEXT_TELEMETRY_DISABLED"] = "1"
    npx = "npx.cmd" if os.name == "nt" else "npx"
    web = subprocess.Popen(
        [npx, "next", "dev", "-H", "127.0.0.1", "-p", str(web_port)],
        cwd=_WEB,
        env=web_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        _wait_http(f"{api_origin}/healthz")
        _wait_http(f"{web_origin}/login")
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
    except Exception:
        _stop(web)
        _stop(api)
        raise
    return BrowserStack(
        page=page,
        web_origin=web_origin,
        username=_USERNAME,
        password=_PASSWORD,
        _browser=browser,
        _playwright=playwright,
        _api=api,
        _web=web,
    )

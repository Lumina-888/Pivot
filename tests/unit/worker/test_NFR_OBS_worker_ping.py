from __future__ import annotations

import urllib.request

from pivot_worker.health import start_health_server


def test_NFR_OBS_worker_ping_serves_healthz():
    server, thread, port = start_health_server(host="127.0.0.1", port=0)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as response:
            body = response.read()
            status = response.status
    finally:
        server.shutdown()
        thread.join(timeout=2)
    assert status == 200
    assert b"ok" in body

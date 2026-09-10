"""Worker ping. This is a fixture health endpoint, not a public /api/v1 route."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

_OK = b'{"status":"ok"}'


def ping() -> dict[str, str]:
    return {"status": "ok"}


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"/healthz", "/readyz"}:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(_OK)))
            self.end_headers()
            self.wfile.write(_OK)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def start_health_server(*, host: str, port: int) -> tuple[ThreadingHTTPServer, Thread, int]:
    server = ThreadingHTTPServer((host, port), _HealthHandler)
    thread = Thread(target=server.serve_forever, name="pivot-worker-health", daemon=True)
    thread.start()
    bound_port = int(server.server_address[1])
    return server, thread, bound_port

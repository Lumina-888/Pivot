"""Start the ingest worker ping process. Queue execution is still not Celery."""

from __future__ import annotations

import time

from pivot_worker.health import start_health_server
from pivot_worker.settings import WorkerSettings


def main() -> None:
    settings = WorkerSettings.from_env()
    start_health_server(host=settings.health_host, port=settings.health_port)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()

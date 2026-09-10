"""Start the ingest Celery worker. Health ping remains on /healthz."""

from __future__ import annotations

from pivot_worker.celery_app import start_celery_worker
from pivot_worker.health import start_health_server
from pivot_worker.settings import WorkerSettings


def main() -> None:
    settings = WorkerSettings.from_env()
    start_health_server(host=settings.health_host, port=settings.health_port)
    start_celery_worker(settings, block=True)


if __name__ == "__main__":
    main()

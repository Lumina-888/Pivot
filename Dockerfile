# Pivot API fixture image. The tag is not GATE-P0-008 verified.
FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY api/pyproject.toml /app/api/pyproject.toml
COPY api/src /app/api/src

RUN pip install "./api[http,postgres,minio,qdrant,redis]"

EXPOSE 8000

HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()"

CMD ["uvicorn", "pivot.http.main:app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

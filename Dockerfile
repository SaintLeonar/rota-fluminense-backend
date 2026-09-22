FROM python:3.14.5-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --create-home --home-dir /home/app app

COPY requirements.txt ./

RUN python -m pip install --no-cache-dir --requirement requirements.txt

COPY --chown=app:app alembic.ini app.py ./
COPY --chown=app:app data ./data
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app models ./models
COPY --chown=app:app routes ./routes
COPY --chown=app:app schemas ./schemas
COPY --chown=app:app scripts/__init__.py scripts/seed.py ./scripts/
COPY --chown=app:app services ./services
COPY --chown=app:app utils ./utils
COPY --chown=app:app --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint

USER app

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "-c", "from urllib.request import urlopen; response = urlopen('http://127.0.0.1:5000/locais?pagina=1&por_pagina=1', timeout=3); raise SystemExit(0 if response.status == 200 else 1)"]

ENTRYPOINT ["docker-entrypoint"]

CMD ["gunicorn", "--workers", "1", "--worker-class", "sync", "--bind", "0.0.0.0:5000", "--access-logfile=-", "--error-logfile=-", "app:app"]

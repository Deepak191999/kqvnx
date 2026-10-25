# Backend image. The SQLite snapshot is baked in, so a deployed container
# serves the January 2026 analysis without reaching out to Elexon at runtime.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data/wind.db ./data/wind.db

# Run unprivileged.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /srv
USER appuser

ENV DB_PATH=/srv/data/wind.db \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health').read()"

# Heroku and similar platforms inject $PORT, so bind to it rather than a literal.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

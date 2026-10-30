# TasteOS API — production image
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TASTEOS_MODE=demo \
    API_HOST=0.0.0.0 \
    API_PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml apps/api/README.md* ./
COPY apps/api/app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000

# Many hosts inject PORT; default 8000 for local Docker.
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

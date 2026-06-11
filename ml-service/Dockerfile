# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:81ada6cb56bcbe3909644b4cb76ebe5354c65eaaad788a437bc1340a7638d49d AS builder
WORKDIR /build
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev -o requirements.txt && \
    python -m venv /venv && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:81ada6cb56bcbe3909644b4cb76ebe5354c65eaaad788a437bc1340a7638d49d
WORKDIR /app
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/* && \
    adduser --disabled-password --gecos "" appuser && \
    mkdir -p /app/models && chown appuser /app/models
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
USER appuser
COPY src/ ./src/
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
CMD ["python", "src/main.py"]

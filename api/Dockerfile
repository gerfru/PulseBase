# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:44dd04494ee8f3b538294360e7c4b3acb87c8268e4d0a4828a6500b1eff50061 AS builder
WORKDIR /build
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev -o requirements.txt && \
    python -m venv /venv && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:44dd04494ee8f3b538294360e7c4b3acb87c8268e4d0a4828a6500b1eff50061
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    apt-get upgrade -y && rm -rf /var/lib/apt/lists/* && \
    adduser --disabled-password --gecos "" appuser
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
USER appuser
COPY src/ ./src/
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:8000/ready || exit 1
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]

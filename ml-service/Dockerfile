# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:c845af9399020c7e562969a13689e929074a10fd057acd1b1fad06a2fb068e97 AS builder
WORKDIR /build
RUN python -m venv /venv
COPY pyproject.toml .
RUN /venv/bin/pip install --no-cache-dir .

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:c845af9399020c7e562969a13689e929074a10fd057acd1b1fad06a2fb068e97
WORKDIR /app
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* && \
    adduser --disabled-password --gecos "" appuser && \
    mkdir -p /app/models && chown appuser /app/models
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"
USER appuser
COPY src/ ./src/
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
  CMD find /tmp/ml_alive -mmin -2 || exit 1
CMD ["python", "src/main.py"]

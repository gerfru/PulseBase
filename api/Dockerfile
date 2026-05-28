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
    adduser --disabled-password --gecos "" appuser
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"
USER appuser
COPY src/ ./src/
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

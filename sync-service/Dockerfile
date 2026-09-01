# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:656d12e70054d5fda18a045e2494c96701e9792dd1445f95b3d038df954f57e9 AS builder
WORKDIR /build/sync-service
RUN pip install --no-cache-dir uv
COPY sync-service/pyproject.toml sync-service/uv.lock ./
COPY packages/pulsebase_garmin /build/packages/pulsebase_garmin
RUN UV_PROJECT_ENVIRONMENT=/venv uv sync \
  --frozen --no-dev --no-editable --no-install-project

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:656d12e70054d5fda18a045e2494c96701e9792dd1445f95b3d038df954f57e9
WORKDIR /app
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/* && \
    find /usr/local/lib/python*/ensurepip/_bundled -name "setuptools*.whl" -delete 2>/dev/null; true && \
    find /usr/local/lib/python*/site-packages -maxdepth 1 \( -name "setuptools-70*.dist-info" -o -name "msgpack-1.1*.dist-info" \) -exec rm -rf {} + 2>/dev/null; true && \
    pip install --no-cache-dir "setuptools>=78.1.1" "msgpack>=1.2.1" && \
    adduser --disabled-password --gecos "" appuser
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
USER appuser
COPY sync-service/src/ ./src/
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
CMD ["python", "src/main.py"]

# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:3.15-slim@sha256:8c13a3f37a6a5b71498228e902c4b9f51c1f7900d49fabf71f9a650c6120e0d0 AS builder
WORKDIR /build/api
RUN pip install --no-cache-dir uv
COPY api/pyproject.toml api/uv.lock ./
COPY packages/pulsebase_garmin /build/packages/pulsebase_garmin
RUN UV_PROJECT_ENVIRONMENT=/venv uv sync \
    --frozen --no-dev --no-editable --no-install-project

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.15-slim@sha256:8c13a3f37a6a5b71498228e902c4b9f51c1f7900d49fabf71f9a650c6120e0d0
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    apt-get upgrade -y && rm -rf /var/lib/apt/lists/* && \
    find /usr/local/lib/python*/ensurepip/_bundled -name "setuptools*.whl" -delete 2>/dev/null; true && \
    find /usr/local/lib/python*/site-packages -maxdepth 1 \( -name "setuptools-70*.dist-info" -o -name "msgpack-1.1*.dist-info" \) -exec rm -rf {} + 2>/dev/null; true && \
    pip install --no-cache-dir "setuptools>=78.1.1" "msgpack>=1.2.1" && \
    python -m pip uninstall --yes pip && \
    adduser --disabled-password --gecos "" appuser
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
USER appuser
COPY api/src/ ./src/
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:8000/ready || exit 1
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]

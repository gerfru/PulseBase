# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4 AS builder
WORKDIR /build
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev -o requirements.txt && \
    python -m venv /venv && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4
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
COPY src/ ./src/
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
CMD ["python", "src/main.py"]

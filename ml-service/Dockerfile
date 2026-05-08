FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir . && \
    adduser --disabled-password --gecos "" appuser && \
    mkdir -p /app/models && chown appuser /app/models
USER appuser
COPY src/ ./src/
CMD ["python", "src/main.py"]

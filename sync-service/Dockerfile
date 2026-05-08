FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir . && \
    adduser --disabled-password --gecos "" appuser
USER appuser
COPY src/ ./src/
CMD ["python", "src/main.py"]

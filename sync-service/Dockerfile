FROM python:3.14-slim@sha256:a7185a8e40af01bf891414a4df16ef10fc6000cee460a404a13da9029fe41604
WORKDIR /app
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir . && \
    adduser --disabled-password --gecos "" appuser
USER appuser
COPY src/ ./src/
CMD ["python", "src/main.py"]

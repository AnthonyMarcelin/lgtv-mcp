FROM python:3.12-slim

RUN useradd --create-home --uid 1000 --shell /bin/bash appuser

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir . \
    && mkdir -p /data/backups \
    && chown -R appuser:appuser /data /app

USER appuser

ENV DATA_DIR=/data
ENV MCP_BIND_HOST=0.0.0.0
ENV MCP_PORT=8765

CMD ["python", "-m", "lgtv_mcp"]

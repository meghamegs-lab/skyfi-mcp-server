FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python package
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

# Create data directory for SQLite
RUN mkdir -p /data

ENV SKYFI_MCP_DATA_DIR=/data
ENV PORT=8000

EXPOSE 8000

CMD ["skyfi-mcp", "serve", "--host", "0.0.0.0", "--port", "8000"]

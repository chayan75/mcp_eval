# AWS App Runner Dockerfile for MCP Evaluation Server
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY pyproject.toml README.md ./

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[dev,aws,benchmark,anthropic,rest]"

# Copy application code
COPY mcp_eval_server/ ./mcp_eval_server/
COPY startup_proxy.py ./

# Create directories for data
RUN mkdir -p /app/data/cache /app/data/results

# Create startup script
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'set -euo pipefail' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo 'echo "🚀 Starting MCP Evaluation Server on AWS App Runner..."' >> /app/start.sh && \
    echo 'echo "📡 Protocols: HTTP REST API + MCP Wrapper (SSE) via Proxy"' >> /app/start.sh && \
    echo 'echo "🌍 Port: ${PORT:-8080}"' >> /app/start.sh && \
    echo 'echo "🔗 Host: 0.0.0.0"' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Start the proxy server (which manages both REST API and MCP wrapper)' >> /app/start.sh && \
    echo 'exec python3 startup_proxy.py' >> /app/start.sh

RUN chmod +x /app/start.sh

# Expose ports
EXPOSE 8080 9001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Run the application
CMD ["/app/start.sh"]

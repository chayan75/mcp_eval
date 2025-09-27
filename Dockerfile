# AWS App Runner Dockerfile for MCP Evaluation Server
FROM --platform=linux/amd64 python:3.11-slim

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

# Make startup script executable
RUN chmod +x /app/startup_proxy.py

# Expose ports
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Run the application
CMD ["python3", "/app/startup_proxy.py"]

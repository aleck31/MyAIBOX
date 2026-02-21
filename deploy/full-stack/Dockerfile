# Dynamic deployment Dockerfile for MyAIBOX
FROM python:3.12-slim

# Install system dependencies including git
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Create startup script
RUN cat > /app/start.sh << 'EOF'
#!/bin/bash
set -e

echo "Pulling latest code from GitHub..."
if [ -d "/app/my-aibox" ]; then
    cd /app/my-aibox
    git pull origin main
else
    git clone https://github.com/aleck31/my-aibox.git /app/my-aibox
    cd /app/my-aibox
fi

echo "Installing dependencies..."
uv sync --no-cache

echo "Creating necessary directories..."
mkdir -p logs tmp

echo "Starting application..."
uv run uvicorn app:app --host 0.0.0.0 --port 8080
EOF

RUN chmod +x /app/start.sh && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start command
CMD ["/app/start.sh"]

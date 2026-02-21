FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

# Install dependencies first (for caching)
COPY requirements-agentcore.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir aws-opentelemetry-distro==0.12.2

# Runtime hint only; all environment config is injected at deploy time via --env
ENV PYTHONUNBUFFERED=1

# Copy application code
COPY . .

# Create non-root user and fix permissions (after COPY)
RUN useradd -m -u 1000 bedrock_agentcore && \
    mkdir -p /app/logs /app/tmp && \
    chown -R bedrock_agentcore:bedrock_agentcore /app

# Switch to non-root user
USER bedrock_agentcore

EXPOSE 8080
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ping || exit 1

# Run with OpenTelemetry instrumentation
CMD ["opentelemetry-instrument", "python", "-m", "agentcore_app"]

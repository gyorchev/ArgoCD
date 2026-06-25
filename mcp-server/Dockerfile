# Multi-stage ARM64 image for MCP server
# Stage 1: download kubectl binary
FROM debian:bookworm-slim AS kubectl-download

RUN apt-get update && apt-get install -y curl ca-certificates && \
    KUBECTL_VERSION=$(curl -sL https://dl.k8s.io/release/stable.txt) && \
    curl -sLo /kubectl https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/arm64/kubectl && \
    chmod +x /kubectl

# Stage 2: final image
FROM python:3.12-slim

# Copy kubectl from stage 1
COPY --from=kubectl-download /kubectl /usr/local/bin/kubectl

# Install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# Non-root user for security
RUN useradd -m -u 1000 mcp
USER mcp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["python3", "server.py", "8000"]

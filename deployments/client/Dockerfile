FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy minimal requirements for client mode
COPY deployments/client/requirements-client.txt .

# Install only client dependencies (no ML/vector libraries needed)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-client.txt

# Copy only the specific files needed for client mode
# Client only needs rag_processor.py and lightweight API client
RUN mkdir -p ./core ./api
COPY core/rag_processor.py ./core/
COPY api/__init__.py.client ./api/__init__.py
COPY api/client.py ./api/

# Create non-root user
RUN useradd -m -u 1000 mcpuser && \
    chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# MCP server runs on stdin/stdout (no port binding needed)
# Port 3000 is just for reference, not actually used by stdio MCP
EXPOSE 3000

# Health check - verify Python and imports work
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import sys; from dotenv import load_dotenv; sys.exit(0)"

# Start the MCP client in client mode (IS_SERVER=false in .env)
# This will forward all MCP requests to REMOTE_API_URL
CMD ["python3", "-m", "core.rag_processor"]
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy minimal requirements for client
COPY requirements-client.txt .

# Install only client dependencies (no ML/vector libraries needed)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-client.txt

# Copy only the core MCP code (no operations/data needed - those run on server)
COPY ../../core/ ./core/
COPY ../../api/api.py ./api/api.py
COPY ../../api/__init__.py ./api/__init__.py

# Create non-root user
RUN useradd -m -u 1000 mcpuser && \
    chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# MCP server runs on stdin/stdout (no port needed)
# But expose a port for health checks if needed
EXPOSE 3000

# Health check (simple Python script)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# Start the MCP client (reads from stdin, writes to stdout)
CMD ["python3", "core/rag_processor.py"]
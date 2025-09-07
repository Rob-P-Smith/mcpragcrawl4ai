FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from PyPI
RUN pip install --no-cache-dir \
    sentence-transformers==5.1.0 \
    numpy==2.3.2 \
    requests==2.32.5 \
    sqlite-vec \
    mcpo

# Install PyTorch CPU version
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Copy all necessary Python files into the image
COPY crawl4ai_rag_optimized.py .
COPY dbstats.py .
COPY batch_crawler.py .
COPY domains.txt .

# Create directory for database persistence
RUN mkdir -p /app/data

# Create non-root user for security and set permissions
RUN useradd -m -u 1000 mcpuser && chown -R mcpuser:mcpuser /app
USER mcpuser
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8765/docs || exit 1
# Start mcpo automatically with MCP server, no API key by default
CMD ["mcpo", "--host", "0.0.0.0", "--port", "8765", "--", "python3", "crawl4ai_rag_optimized.py"]
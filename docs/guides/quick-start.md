# Quick Start Guide

This guide provides step-by-step instructions for getting started with the Crawl4AI RAG MCP Server.

## Prerequisites

- Ubuntu/Linux system
- Docker installed
- Python 3.8 or higher
- LM-Studio installed (optional)
- At least 4GB RAM available
- 10GB free disk space

## Step 1: Clone Repository

```bash
git clone https://github.com/Rob-P-Smith/mcpragcrawl4ai.git
cd mcpragcrawl4ai
```

## Step 2: Setup Crawl4AI Service

Start the Crawl4AI Docker container:

```bash
# Quick start - single command
docker run -d \
  --name crawl4ai \
  --network crawler_default \
  -p 11235:11235 \
  --shm-size=1gb \
  --restart unless-stopped \
  unclecode/crawl4ai:latest

# Verify container is running
docker ps | grep crawl4ai
```

## Step 3: Test Crawl4AI Service

Verify the Crawl4AI container is working:

```bash
# Wait for container to be ready
sleep 10

# Test basic connectivity
curl http://localhost:11235/

# Test crawling functionality
curl -X POST http://localhost:11235/crawl \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://httpbin.org/html"]}'
```

Expected response should include `"success": true` and crawled content.

## Step 4: Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Upgrade pip
pip install --upgrade pip
```

## Step 5: Install Dependencies

Install all required Python packages from requirements.txt:

```bash
pip install -r requirements.txt
```

This installs:
- sentence-transformers (for embeddings)
- sqlite-vec (for vector search)
- FastAPI & uvicorn (for REST API)
- And all other dependencies

## Step 6: Configure Environment

Create a `.env` file in the project root:

```bash
cat > .env << EOF
IS_SERVER=true
LOCAL_API_KEY=$(openssl rand -base64 32)
DB_PATH=./data/crawl4ai_rag.db
CRAWL4AI_URL=http://localhost:11235
LOG_LEVEL=INFO
EOF
```

## Step 7: Test MCP Server

Test the MCP server with manual JSON-RPC calls:

```bash
# Test tools listing
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | python3 core/rag_processor.py

# Test crawling and storing
echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "crawl_and_remember", "arguments": {"url": "https://httpbin.org/html"}}}' | python3 core/rag_processor.py
```

## Step 8: Configure LM-Studio (Optional)

If using LM-Studio, update the MCP configuration:

```bash
# Get the full paths
VENV_PATH=$(pwd)/.venv
SCRIPT_PATH=$(pwd)/core/rag_processor.py

echo "Virtual Environment: $VENV_PATH/bin/python3"
echo "Script Path: $SCRIPT_PATH"
```

In LM-Studio, go to **Program → View MCP Configuration** and update `mcp.json`:

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "/full/path/to/.venv/bin/python3",
      "args": ["/full/path/to/core/rag_processor.py"]
    }
  }
}
```

Replace with your actual absolute paths.

## Step 9: Verify LM-Studio Integration

1. **Restart LM-Studio completely** (close and reopen)
2. **Check Integrations panel** - should show `crawl4ai-rag` with blue toggle
3. **Verify available tools**:

   **Basic Tools:**
   - `crawl_url` - Crawl single page without storing
   - `crawl_and_remember` - Crawl single page and store permanently
   - `crawl_temp` - Crawl single page and store temporarily

   **Deep Crawling Tools:**
   - `deep_crawl_dfs` - Deep crawl multiple pages without storing
   - `deep_crawl_and_store` - Deep crawl and store all pages

   **Knowledge Management:**
   - `search_memory` - Search stored content using semantic similarity
   - `list_memory` - List all stored content
   - `forget_url` - Remove specific content by URL
   - `clear_temp_memory` - Clear session content

4. **Test with simple command**: "List what's in memory"

## Alternative: Docker Deployment

For a production-ready deployment, see the [Deployment Guide](../deployments.md) for Docker-based options:

- **Server Deployment**: Full REST API + MCP server in Docker
- **Client Deployment**: Lightweight client forwarding to remote server

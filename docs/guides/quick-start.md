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
# Server Configuration
IS_SERVER=true
LOCAL_API_KEY=$(openssl rand -base64 32)

# Database Configuration
DB_PATH=./data/crawl4ai_rag.db
USE_MEMORY_DB=true  # Enable RAM database for 10-50x faster performance

# Service Configuration
CRAWL4AI_URL=http://localhost:11235

# Logging
LOG_LEVEL=INFO

# Optional: Security Configuration
BLOCKED_DOMAIN_KEYWORD=$(openssl rand -base64 16)  # For unblocking domains
EOF
```

### Environment Variables Explained

- **USE_MEMORY_DB=true**: Enables high-performance RAM database mode
  - 10-50x faster read operations
  - 5-10x faster write operations
  - Automatic synchronization to disk every 5 seconds
  - Periodic backup sync every 5 minutes
  - See [RAM Database Mode](../../docs/advanced/ram-database.md) for details

- **LOCAL_API_KEY**: Authentication key for REST API access
  - Generated securely using `openssl rand -base64 32`
  - Required for all API endpoints except `/health`

- **BLOCKED_DOMAIN_KEYWORD**: Authorization keyword for unblocking domains
  - Optional but recommended for security
  - Required to remove domain patterns from blocklist
  - Keep this secret and secure

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

## Step 10: Verify System Status

Check that all systems are operational and RAM database is active:

```bash
# Export your API key (use the one from your .env file)
export API_KEY=$(grep LOCAL_API_KEY .env | cut -d'=' -f2)

# Check system health
curl http://localhost:8080/health

# Check detailed status
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/status

# Check database statistics (should show using_ram_db: true)
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/stats | jq '.data.using_ram_db'

# Check RAM database sync health
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/db/stats
```

Expected output for `/api/v1/stats`:
```json
{
  "success": true,
  "data": {
    "using_ram_db": true,
    "total_pages": 0,
    "database_size_mb": 0.02,
    "retention_breakdown": {
      "permanent": 0,
      "session_only": 0,
      "30_days": 0
    }
  }
}
```

## Step 11: Test Domain Blocking (Optional)

The system comes with pre-configured domain blocks for security:

```bash
# List blocked domains
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/blocked-domains

# Add a custom blocked pattern
curl -X POST http://localhost:8080/api/v1/blocked-domains \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"pattern": "*.spam-site.com", "description": "Known spam domain"}'

# Test that blocked URLs are rejected
curl -X POST http://localhost:8080/api/v1/crawl \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.spam-site.com/page"}'
# Should return: "URL is blocked by domain pattern: *.spam-site.com"
```

Default blocked patterns:
- `*.ru` - All Russian domains
- `*.cn` - All Chinese domains
- `*porn*` - URLs containing "porn"
- `*sex*` - URLs containing "sex"
- `*escort*` - URLs containing "escort"
- `*massage*` - URLs containing "massage"

See [Security Documentation](../../docs/advanced/security.md) for more details.

## Step 12: Test Basic Functionality

Try crawling and searching:

```bash
# Crawl and store a page
curl -X POST http://localhost:8080/api/v1/crawl/store \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "tags": "test,example"}'

# Search for content
curl -X POST http://localhost:8080/api/v1/search \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "example domain", "limit": 5}'

# List stored content
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/memory

# Check updated stats
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/stats
```

## Performance Tips

### RAM Database Mode
With `USE_MEMORY_DB=true`, you'll experience:
- **Instant queries**: Vector similarity searches complete in milliseconds
- **Fast storage**: Pages are stored 5-10x faster than disk mode
- **Automatic persistence**: Changes sync to disk every 5 seconds after writes
- **Reliability**: Periodic backup sync every 5 minutes

Monitor sync health:
```bash
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/db/stats
```

Key metrics to watch:
- `pending_changes`: Should be 0 or low (under 100)
- `last_sync_ago_seconds`: Should be under 300 (5 minutes)
- `sync_success_rate`: Should be 1.0 (100%)

### If You Need Disk Mode
To disable RAM mode and use traditional disk database:

```bash
# Edit .env file
USE_MEMORY_DB=false

# Restart the server
# RAM mode is ~10-50x faster, but uses more memory (~50-500MB)
```

## Troubleshooting

### RAM Database Not Initializing
**Symptom**: `using_ram_db: false` in stats

**Solutions**:
1. Check `.env` file: `USE_MEMORY_DB=true`
2. Restart the server after changing environment variables
3. Check logs for initialization errors
4. Verify sufficient RAM available (need at least 500MB free)

### Sync Health Issues
**Symptom**: High `pending_changes` or old `last_sync_time`

**Solutions**:
1. Check `/api/v1/db/stats` for sync metrics
2. Look for sync errors in application logs
3. Verify disk space available
4. Restart server to force full sync

### Domain Blocking Not Working
**Symptom**: Blocked URLs are still being crawled

**Solutions**:
1. Verify pattern is in blocklist: `GET /api/v1/blocked-domains`
2. Check pattern syntax (`*.ru` for TLD, `*keyword*` for content)
3. Test with exact URL to see blocking reason
4. Restart server if recently added blocks

See [Troubleshooting Guide](troubleshooting.md) for more detailed solutions.

## Next Steps

Now that your system is running:

1. **Explore the API**: See [API Endpoints](../../docs/api/endpoints.md) for all available endpoints
2. **Learn Security Features**: Review [Security Documentation](../../docs/advanced/security.md)
3. **Optimize Performance**: Read [RAM Database Mode](../../docs/advanced/ram-database.md)
4. **Deep Crawling**: Check out [Batch Operations](../../docs/advanced/batch-operations.md)

## Alternative: Docker Deployment

For a production-ready deployment, see the [Deployment Guide](deployment.md) for Docker-based options:

- **Server Deployment**: Full REST API + MCP server in Docker
- **Client Deployment**: Lightweight client forwarding to remote server

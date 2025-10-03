# Complete Distributed Setup Plan: Server Docker + Remote Client MCP

## Architecture Overview
Your setup will have two components:
1. **Ubuntu Server (192.168.10.50)**: Runs API server in Docker alongside Crawl4AI container
2. **Development Laptop (WSL)**: Runs MCP client that forwards all calls to the server's API

## Part 1: Server Docker Deployment (192.168.10.50)

### A. Prepare the API Server Docker Container
1. **Create new Dockerfile for API server** (`Dockerfile.api`):
   - Base image: python:3.11-slim
   - Install dependencies (FastAPI, uvicorn, sentence-transformers, sqlite-vec)
   - Copy API code and dependencies
   - Expose port 8080 for REST API

2. **Update docker-compose.yml**:
   - Keep existing crawl4ai service
   - Add new api-server service:
     - Build from Dockerfile.api
     - Port mapping: 8080:8080
     - Volume: ./data:/app/data (for database persistence)
     - Environment variables for server mode
     - Network: shared with crawl4ai

3. **Database Location**:
   - SQLite database will be at `./data/crawl4ai_rag.db` on host
   - Persisted via Docker volume mount
   - Accessible across container restarts

### B. Configure Server Environment
Create `.env.server` file:
```
IS_SERVER=true
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
LOCAL_API_KEY=generate-secure-key-here
DB_PATH=/app/data/crawl4ai_rag.db
CRAWL4AI_URL=http://crawl4ai:11235
```

## Part 2: Client Setup on Development Laptop (WSL)

### A. Install MCP Client
1. **Clone repository** to WSL environment
2. **Create Python virtual environment**
3. **Install minimal dependencies** (no need for Docker on client)

### B. Configure Client Environment
Create `.env` file on laptop:
```
IS_SERVER=false
REMOTE_API_URL=http://192.168.10.50:8080
REMOTE_API_KEY=same-key-as-server
```

### C. Configure LM-Studio (or other inference provider)
Update MCP configuration to point to local MCP client:
```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "python3",
      "args": ["/path/to/core/rag_processor.py"],
      "env": {
        "IS_SERVER": "false",
        "REMOTE_API_URL": "http://192.168.10.50:8080",
        "REMOTE_API_KEY": "your-api-key"
      }
    }
  }
}
```

## Part 3: How the Flow Works

### 1. Client Request Flow:
   - LM-Studio sends MCP tool call to local rag_processor.py
   - rag_processor.py detects IS_SERVER=false (client mode)
   - Uses APIClient to convert MCP call to REST API request
   - Sends HTTP request to 192.168.10.50:8080

### 2. Server Processing:
   - API server receives authenticated request
   - Executes the action (crawl, search, store)
   - For crawling: calls Crawl4AI container internally
   - For RAG: queries SQLite database with vector search
   - Returns JSON response

### 3. Response Flow:
   - Server sends JSON response back to client
   - Client converts API response to MCP format
   - Returns to LM-Studio for use in inference

## Part 4: Network Requirements

- **Port 8080**: Must be accessible from laptop to server
- **Firewall**: Allow incoming connections on 8080 from LAN
- **No port forwarding needed** (same LAN)
- **API Authentication**: Protects against unauthorized access

## Part 5: Testing Steps

### 1. Test server API directly:
```bash
curl -X GET http://192.168.10.50:8080/health
curl -X POST http://192.168.10.50:8080/api/v1/search \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

### 2. Test client MCP:
```bash
# On laptop in WSL
python3 core/rag_processor.py
# Send test JSON-RPC request via stdin
```

### 3. Test end-to-end with LM-Studio:
   - Configure MCP server
   - Use a tool like "search_memory"
   - Verify results come from server database

## Benefits of This Architecture

This architecture gives you:
- **Centralized database** on server
- **Shared crawling resources** - one Crawl4AI instance serves all clients
- **Multiple clients can connect** - each developer can have their own MCP client
- **Clean separation of concerns** - server handles heavy lifting, clients are lightweight
- **Easy backup** - just backup ./data directory on server
- **Scalable** - can add more clients without impacting server
- **Secure** - API key authentication and LAN-only access
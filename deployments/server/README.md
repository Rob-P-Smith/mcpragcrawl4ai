# Crawl4AI RAG Server Deployment

This directory contains the Docker deployment configuration for the Crawl4AI RAG API server and MCP server.

## Prerequisites

- Docker and Docker Compose v2 installed
- Crawl4AI container running on the `crawler_default` network
- Ports 8080 (REST API) and 3000 (MCP server) available

## Architecture

```
┌─────────────────┐
│   LM Studio     │
│  (MCP Client)   │
└────────┬────────┘
         │ socat stdio-over-TCP
         │
    Port 3000
         │
┌────────▼────────┐      ┌──────────────┐
│  MCP Server     │──────│  Crawl4AI    │
│  (port 3000)    │      │ (port 11235) │
└─────────────────┘      └──────────────┘
         │
         │ Shared Database
         │
┌────────▼────────┐      ┌──────────────┐
│  REST API       │──────│  SQLite DB   │
│  (port 8080)    │      │   + Vectors  │
└─────────────────┘      └──────────────┘
```

## Quick Start

### 1. Configure Environment

Edit `deployments/server/.env`:

```bash
# Server Configuration
IS_SERVER=true
SERVER_HOST=0.0.0.0
SERVER_PORT=8080

# Remote Server Configuration (for client mode - not used in server mode)
REMOTE_API_URL=https://192.168.10.50:8080
REMOTE_API_KEY=aSYERYg8RP9TQ+h+4fvJ4RGSc5ioq5Evg5Gmlp801+8=

# Local API Authentication (IMPORTANT: Change this!)
LOCAL_API_KEY=aSYERYg8RP9TQ+h+4fvJ4RGSc5ioq5Evg5Gmlp801+8=

# Database Configuration
DB_PATH=/app/data/crawl4ai_rag.db

# Crawl4AI Service (internal Docker network)
CRAWL4AI_URL=http://crawl4ai:11235

# Security Settings
ENABLE_CORS=true
MAX_REQUEST_SIZE=10485760
RATE_LIMIT_PER_MINUTE=60

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/data/crawl4ai_api.log
```

**Generate a secure API key:**
```bash
openssl rand -base64 32
```

### 2. Ensure Crawl4AI is Running

The API server connects to the Crawl4AI container via the `crawler_default` network:

```bash
# Check if Crawl4AI is running
docker ps | grep crawl4ai

# If not running, start it (adjust path to your Crawl4AI setup)
cd /path/to/your/crawl4ai
docker-compose up -d
```

### 3. Build and Start Services

From the project root (`/home/robiloo/Documents/mcpragcrawl4ai`):

```bash
# Stop any existing containers
docker stop crawl4ai-api-server crawl4ai-mcp-server 2>/dev/null
docker rm crawl4ai-api-server crawl4ai-mcp-server 2>/dev/null

# Build the images
docker compose -f deployments/server/docker-compose.yml build

# Start both services
docker compose -f deployments/server/docker-compose.yml up -d

# Or start individually:
# docker compose -f deployments/server/docker-compose.yml up -d api-server
# docker compose -f deployments/server/docker-compose.yml up -d mcp-server
```

### 4. Verify Deployment

**Check service status:**
```bash
docker compose -f deployments/server/docker-compose.yml ps
```

**Test REST API:**
```bash
# Health check (no auth required)
curl http://localhost:8080/health

# Status check (requires API key)
curl -H "Authorization: Bearer aSYERYg8RP9TQ+h+4fvJ4RGSc5ioq5Evg5Gmlp801+8=" \
  http://localhost:8080/api/v1/status
```

**Test MCP Server:**
```bash
# Install socat on your host if not already installed
sudo apt-get install socat

# Test MCP connection (should wait for JSON-RPC input)
socat - TCP:localhost:3000
```

## Services

### api-server (Port 8080)
- **Container:** crawl4ai-api-server
- **Purpose:** REST API for external clients
- **Endpoints:** See http://localhost:8080/docs
- **Authentication:** Bearer token (LOCAL_API_KEY)

### mcp-server (Port 3000)
- **Container:** crawl4ai-mcp-server
- **Purpose:** MCP protocol server for LM Studio
- **Transport:** stdio over TCP (via socat)
- **Protocol:** JSON-RPC over stdio

## Database

- **Type:** SQLite with sqlite-vec extension
- **Location:** `/home/robiloo/Documents/mcpragcrawl4ai/data/crawl4ai_rag.db`
- **Mounted:** Shared volume between containers
- **Persistence:** Data persists across container restarts

**Schema:**
- `crawled_content` - Stores web page content with metadata
- `content_vectors` - Vector embeddings (384-dim) for semantic search

## LM Studio Configuration

To connect LM Studio to the MCP server:

**File:** `~/.config/lm-studio/mcp-settings.json` (or similar)

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "socat",
      "args": [
        "-",
        "TCP:localhost:3000"
      ]
    }
  }
}
```

**Prerequisites:**
- Install socat: `sudo apt-get install socat`
- Ensure port 3000 is accessible from LM Studio host

## Management Commands

### View Logs
```bash
# All services
docker compose -f deployments/server/docker-compose.yml logs -f

# Specific service
docker compose -f deployments/server/docker-compose.yml logs -f api-server
docker compose -f deployments/server/docker-compose.yml logs -f mcp-server
```

### Restart Services
```bash
# Restart all
docker compose -f deployments/server/docker-compose.yml restart

# Restart specific service
docker compose -f deployments/server/docker-compose.yml restart api-server
```

### Stop Services
```bash
docker compose -f deployments/server/docker-compose.yml down

# Stop and remove volumes (WARNING: deletes database!)
docker compose -f deployments/server/docker-compose.yml down -v
```

### Rebuild After Code Changes
```bash
# Rebuild and restart
docker compose -f deployments/server/docker-compose.yml build
docker compose -f deployments/server/docker-compose.yml up -d
```

## Troubleshooting

### API Server Not Reachable
1. Check if container is running: `docker ps | grep api-server`
2. Check logs: `docker logs crawl4ai-api-server`
3. Verify port 8080 is not blocked: `netstat -ln | grep 8080`
4. Test Crawl4AI connection from inside container:
   ```bash
   docker exec -it crawl4ai-api-server curl http://crawl4ai:11235/
   ```

### MCP Server Not Responding
1. Check if container is running: `docker ps | grep mcp-server`
2. Check logs: `docker logs crawl4ai-mcp-server`
3. Test TCP connection: `telnet localhost 3000`
4. Verify socat is working inside container:
   ```bash
   docker exec -it crawl4ai-mcp-server ps aux | grep socat
   ```

### Crawl4AI Connection Failed
1. Ensure Crawl4AI container is running:
   ```bash
   docker ps | grep crawl4ai
   ```
2. Check if both containers are on same network:
   ```bash
   docker network inspect crawler_default
   ```
3. Test connection from API container:
   ```bash
   docker exec -it crawl4ai-api-server curl http://crawl4ai:11235/
   ```

### Database Issues
1. Check file permissions:
   ```bash
   ls -la /home/robiloo/Documents/mcpragcrawl4ai/data/
   ```
2. Verify database is accessible:
   ```bash
   docker exec -it crawl4ai-api-server sqlite3 /app/data/crawl4ai_rag.db ".tables"
   ```

## API Documentation

Once running, interactive API documentation is available at:
- **Swagger UI:** http://localhost:8080/docs
- **ReDoc:** http://localhost:8080/redoc
- **OpenAPI JSON:** http://localhost:8080/openapi.json

## Security Notes

1. **Change default API key** - Never use default keys in production
2. **Use HTTPS** - Deploy behind reverse proxy with TLS
3. **Restrict network access** - Use firewall rules to limit who can access ports 8080 and 3000
4. **Regular backups** - Backup the database regularly
5. **Update dependencies** - Keep Docker images and Python packages updated

## Performance Tips

1. **Database optimization:**
   ```bash
   docker exec -it crawl4ai-api-server sqlite3 /app/data/crawl4ai_rag.db "VACUUM;"
   ```

2. **Monitor resource usage:**
   ```bash
   docker stats crawl4ai-api-server crawl4ai-mcp-server
   ```

3. **Adjust rate limits** in `.env` if needed:
   ```bash
   RATE_LIMIT_PER_MINUTE=100
   ```

## Network Configuration

Both services connect to the external `crawler_default` network created by the Crawl4AI deployment:

```bash
# View network details
docker network inspect crawler_default

# If network doesn't exist, create it:
docker network create crawler_default
```

## File Structure

```
deployments/server/
├── docker-compose.yml    # Multi-service deployment config
├── Dockerfile.api        # Image definition (used by both services)
├── .env                  # Environment variables (DO NOT COMMIT!)
├── requirements.txt      # Python dependencies
├── start_api_server.py   # REST API entrypoint
└── README.md            # This file

../../data/               # Shared data directory
└── crawl4ai_rag.db      # SQLite database (created on first run)
```

## Version Information

- **Python:** 3.11-slim
- **Crawl4AI:** v0.7.0-r1 (external container)
- **FastAPI:** 0.115.6
- **sentence-transformers:** 3.2.1 (all-MiniLM-L6-v2 model)
- **sqlite-vec:** 0.1.6

---

For issues or questions, see the test report at `deployments/server/report.md`

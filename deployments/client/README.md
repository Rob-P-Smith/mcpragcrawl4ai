# Crawl4AI RAG MCP Client Deployment

Lightweight MCP client for Windows, macOS, or Linux that connects to a remote Crawl4AI RAG server.

## Overview

This client deployment provides:

- **Lightweight MCP server** that runs in Docker
- **MCP-to-API translation** forwarding all requests to remote server
- **Cross-platform support** for Windows (Docker Desktop), macOS, and Linux
- **Minimal resource usage** - no ML models, no database, just API forwarding
- **Clean local environment** - all dependencies in Docker container

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│     LLM     │ ◄─MCP─► │    Client    │ ◄─HTTP─►│    Server    │
│  (Windows)  │ stdio   │  (MCP→API)   │   REST  │  (Full RAG)  │
└─────────────┘         └──────────────┘         └──────────────┘
Claude Desktop          Docker Container         Remote Linux Server
                        (crawl4ai-rag-client)
```

**How it works:**
1. LLM sends MCP tool requests via stdin/stdout
2. Client container receives MCP JSON-RPC requests
3. Client translates MCP requests → REST API calls
4. Server executes (crawling, embeddings, database operations)
5. Server responds with REST API JSON
6. Client translates REST API responses → MCP responses
7. LLM receives results as MCP tool outputs

## Prerequisites

### Windows
- **Docker Desktop for Windows** with WSL 2 backend
- **PowerShell** or **Git Bash**
- Network access to remote server

### Linux/macOS
- **Docker** and **docker-compose**
- Network access to remote server

## Quick Start

### Option 1: Automated Setup (Windows PowerShell)

```powershell
# Navigate to this directory
cd path\to\mcpragcrawl4ai\deployments\client

# Run setup script
.\setup-client.ps1
```

### Option 2: Manual Setup (All Platforms)

**1. Get server details from your administrator:**
   - Server URL (e.g., `http://192.168.10.50:8080`)
   - API Key (matches server's `LOCAL_API_KEY`)
   - Blocked domain keyword (optional, for admin operations)

**2. Create configuration file:**

**Windows (PowerShell):**
```powershell
cd deployments\client
Copy-Item .env_template.txt .env
notepad .env
```

**Linux/macOS:**
```bash
cd deployments/client
cp .env_template.txt .env
nano .env  # or your preferred editor
```

**3. Update required settings in `.env`:**

```bash
# Set client mode (REQUIRED)
IS_SERVER=false

# Remote server connection (REQUIRED)
REMOTE_API_URL=http://YOUR_SERVER_IP:8080
REMOTE_API_KEY=your_api_key_from_server

# Optional - for admin operations
BLOCKED_DOMAIN_KEYWORD=your_keyword
```

**4. Test server connectivity:**

**Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri "http://YOUR_SERVER_IP:8080/health"
```

**Linux/macOS:**
```bash
curl http://YOUR_SERVER_IP:8080/health
# Should return: {"status":"healthy","timestamp":"..."}
```

**5. Start the client:**

```bash
# From deployments/client directory
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

## LLM Configuration

### Claude Desktop

**Windows:** Edit `%APPDATA%\Claude\claude_desktop_config.json`

**macOS:** Edit `~/Library/Application Support/Claude/claude_desktop_config.json`

**Linux:** Edit `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "docker",
      "args": ["exec", "-i", "crawl4ai-rag-client", "python", "-m", "core.rag_processor"]
    }
  }
}
```

**After updating:** Restart Claude Desktop

### LM Studio

Configure in Settings → Developer → MCP Servers:

**Command:** `docker`

**Args:** `["exec", "-i", "crawl4ai-rag-client", "python", "-m", "core.rag_processor"]`

## Available MCP Tools

All tools execute on the remote server:

- **crawl_url** - Fetch URL without storing
- **crawl_and_remember** - Crawl and store permanently
- **crawl_temp** - Crawl and store temporarily
- **deep_crawl_and_store** - Recursive website crawl
- **search_memory** - Semantic search with tag filtering
- **target_search** - Intelligent search with tag expansion
- **list_memory** - List stored content
- **list_domains** - List unique domains
- **forget_url** - Remove content by URL
- **clear_temp_memory** - Clear session content
- **db_stats** - Database statistics
- **add_blocked_domain** - Block domain pattern
- **remove_blocked_domain** - Unblock domain (requires keyword)
- **list_blocked_domains** - List blocked patterns
- **get_help** - Tool documentation

## Docker Commands

```bash
# Start client
docker compose up -d

# Stop client
docker compose down

# View logs
docker compose logs -f

# Check status
docker compose ps

# Restart after config changes
docker compose down && docker compose up -d

# Rebuild after code updates
docker compose up -d --build
```

## Troubleshooting

See [SETUP.md](SETUP.md) for detailed troubleshooting including:
- Docker Desktop issues (Windows)
- Connection refused errors
- Authentication failures
- Container startup problems
- LLM integration issues

**Quick checks:**
```bash
# Verify container is running
docker compose ps

# Check logs for errors
docker compose logs -f

# Test server connection
curl http://YOUR_SERVER_IP:8080/health

# Verify container name
docker ps --filter "name=crawl4ai-rag-client"
```

## Network Requirements

**Outbound access needed:**
- Remote server on configured port (default: 8080)
- HTTPS if using secure connection

**No inbound ports required** - MCP uses stdin/stdout

## Security

- Keep `.env` file secure (contains API key)
- Use HTTPS for production (`REMOTE_API_URL=https://...`)
- Don't commit `.env` to version control
- Limit `REMOTE_API_KEY` distribution

## Data Storage

**Client stores:** Nothing - stateless API forwarder

**Server stores:** All crawled content, embeddings, and knowledge base data

## Performance

- **Memory:** ~100MB (minimal Python + httpx)
- **CPU:** Negligible (just API forwarding)
- **Network:** Latency depends on server connection
- **Disk:** ~50MB (slim Python image + minimal dependencies)

## Documentation

- **Detailed setup:** [SETUP.md](SETUP.md)
- **Configuration reference:** [.env_template.txt](.env_template.txt)
- **Main project:** [../../README.md](../../README.md)

## Files

- `Dockerfile` - Client container image
- `docker-compose.yml` - Container orchestration
- `.env_template.txt` - Configuration template with documentation
- `.env` - Your configuration (create from template)
- `requirements-client.txt` - Minimal Python dependencies
- `SETUP.md` - Comprehensive setup guide
- `README.md` - This file
- `setup-client.ps1` - Windows PowerShell setup script
- `setup-client.sh` - Linux/macOS setup script

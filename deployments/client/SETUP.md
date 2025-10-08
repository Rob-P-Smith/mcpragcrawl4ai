# Client Deployment Setup Guide

This directory contains the configuration for deploying the lightweight Crawl4AI RAG MCP Client that connects to a remote server.

## What is Client Mode?

Client mode runs a lightweight MCP server that forwards all requests to a remote REST API server. Use this when:

- Your LLM runs on a different machine (e.g., Windows laptop) than the RAG server
- You want minimal resource usage on the client machine
- You need to connect to a centralized RAG knowledge base

**Architecture:**
```
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│     LLM     │ ◄─MCP─► │    Client    │ ◄─HTTP─►│    Server    │
│ (Claude/LM) │         │  (MCP→API)   │         │ (Full RAG)   │
└─────────────┘         └──────────────┘         └──────────────┘
  Windows PC          Docker Container         Remote Linux Server
```

**How It Works:**
1. Your LLM (Claude Desktop, LM Studio) calls MCP tools via stdin/stdout
2. Client container receives MCP JSON-RPC requests
3. Client translates MCP → REST API HTTP requests
4. Server processes requests (crawling, database, embeddings)
5. Server returns REST API responses
6. Client translates API responses → MCP responses
7. Your LLM receives results as MCP tool outputs

## Prerequisites

### Windows Requirements
- **Docker Desktop for Windows** (with WSL 2 backend enabled)
  - Download: https://www.docker.com/products/docker-desktop
  - Enable WSL 2 during installation
  - Ensure it's running before starting
- **PowerShell** or **Git Bash** for commands
- Network access to remote server

### Linux/macOS Requirements
- **Docker** and **docker-compose** installed
- Network access to remote server

## Quick Start

### Windows Setup

#### 1. Install Docker Desktop
1. Download and install Docker Desktop for Windows
2. Enable WSL 2 backend during installation
3. Start Docker Desktop and wait for it to be ready
4. Verify: Open PowerShell and run `docker --version`

#### 2. Get Server Details

Contact your server administrator for:
- **Server URL**: e.g., `http://192.168.10.50:8080` (local network) or `https://myserver.com:8080` (internet)
- **API Key**: The `LOCAL_API_KEY` from the server's `.env` file
- **Blocked Domain Keyword**: Optional, for admin operations

#### 3. Configure Client

**Using PowerShell:**
```powershell
# Navigate to client deployment directory
cd path\to\mcpragcrawl4ai\deployments\client

# Copy the template
Copy-Item .env_template.txt .env

# Edit with your server details using Notepad
notepad .env
```

**Using Git Bash (Windows):**
```bash
# Navigate to client deployment directory
cd /c/path/to/mcpragcrawl4ai/deployments/client

# Copy the template
cp .env_template.txt .env

# Edit with your server details
nano .env  # or use 'code .env' for VS Code
```

#### 4. Update Required Settings

Edit `.env` and update these **required** values:

```bash
# Set to false for client mode (REQUIRED)
IS_SERVER=false

# Your remote server details (REQUIRED)
REMOTE_API_URL=http://YOUR_SERVER_IP:8080
REMOTE_API_KEY=your_api_key_from_server

# Optional - for admin operations
BLOCKED_DOMAIN_KEYWORD=your_keyword_from_server
```

#### 5. Test Server Connectivity

**Windows (PowerShell):**
```powershell
# Test server connectivity
Invoke-WebRequest -Uri "http://YOUR_SERVER_IP:8080/health"
```

**Windows (Git Bash) / Linux / macOS:**
```bash
# Test server connectivity
curl http://YOUR_SERVER_IP:8080/health

# Should return: {"status":"healthy","timestamp":"..."}
```

#### 6. Start the Client

**Windows (PowerShell):**
```powershell
# From deployments/client directory
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

**Linux/macOS:**
```bash
# From deployments/client directory
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### Linux/macOS Setup

Follow steps 2-6 above, using the Linux/macOS command variants.

## Configure Your LLM

### Claude Desktop

**Windows:**
Configuration file location: `%APPDATA%\Claude\claude_desktop_config.json`

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

**macOS:**
Configuration file location: `~/Library/Application Support/Claude/claude_desktop_config.json`

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

**Linux:**
Configuration file location: `~/.config/Claude/claude_desktop_config.json`

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

After updating the config file, restart Claude Desktop.

### LM Studio

LM Studio uses MCP via stdio (not HTTP). Configure in Settings → Developer → MCP Servers:

**Command:** `docker`

**Args:** `["exec", "-i", "crawl4ai-rag-client", "python", "-m", "core.rag_processor"]`

Alternatively, if LM Studio supports config files, add to the MCP configuration:
```json
{
  "crawl4ai-rag": {
    "command": "docker",
    "args": ["exec", "-i", "crawl4ai-rag-client", "python", "-m", "core.rag_processor"]
  }
}
```

## Available Tools

Once connected, your LLM will have access to these MCP tools (all executed on remote server):

### Content Retrieval
- **crawl_url**: Fetch and process a single URL without storing
- **crawl_and_remember**: Crawl URL and store permanently in knowledge base
- **crawl_temp**: Crawl URL and store temporarily (session-only)
- **deep_crawl_and_store**: Recursively crawl website with DFS (depth/page limits)

### Knowledge Base Search
- **search_memory**: Query knowledge base using semantic search with optional tag filtering
- **target_search**: Intelligent search with automatic tag expansion

### Knowledge Base Management
- **list_memory**: List all stored content with pagination
- **list_domains**: List unique domains in knowledge base with page counts
- **forget_url**: Remove specific content by URL
- **clear_temp_memory**: Clear temporary session content
- **db_stats**: Get comprehensive database statistics

### Domain Blocking (Admin)
- **add_blocked_domain**: Add domain pattern to blocklist (supports wildcards)
- **remove_blocked_domain**: Remove domain from blocklist (requires keyword)
- **list_blocked_domains**: View blocked domain patterns

### Help
- **get_help**: Get comprehensive help documentation for all tools

**Note**: All tools execute on the remote server. The client just translates MCP ↔ REST API.

## Troubleshooting

### Docker Desktop Not Running (Windows)

**Symptoms:** `docker` command not found or connection errors

**Solution:**
1. Start Docker Desktop from Start Menu
2. Wait for Docker icon in system tray to show "Docker Desktop is running"
3. Verify: Run `docker --version` in PowerShell

### Connection Refused

**Symptoms:** Client logs show connection errors to `REMOTE_API_URL`

**Diagnose:**

**Windows (PowerShell):**
```powershell
# Test direct connection
Invoke-WebRequest -Uri "http://YOUR_SERVER_IP:8080/health"

# Test network connectivity
Test-NetConnection -ComputerName YOUR_SERVER_IP -Port 8080
```

**Linux/macOS/Git Bash:**
```bash
# Test direct connection
curl http://YOUR_SERVER_IP:8080/health

# Check DNS resolution
ping YOUR_SERVER_IP

# Check firewall
telnet YOUR_SERVER_IP 8080
```

**Common Causes:**
- Server is not running
- Firewall blocking port 8080
- Incorrect server IP in `.env`
- VPN or network configuration issues

### Authentication Failed

**Symptoms:** API returns 401 Unauthorized

**Verify API key:**

**Windows (PowerShell):**
```powershell
$headers = @{ "Authorization" = "Bearer YOUR_API_KEY" }
Invoke-WebRequest -Uri "http://YOUR_SERVER_IP:8080/api/v1/status" -Headers $headers
```

**Linux/macOS/Git Bash:**
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://YOUR_SERVER_IP:8080/api/v1/status
```

**Solution:**
- API key must match server's `LOCAL_API_KEY` exactly
- Check for extra spaces or quotes
- Contact server administrator

### Client Container Won't Start

**Check logs:**

**Windows (PowerShell):**
```powershell
docker compose logs

# Look for specific errors
docker compose logs | Select-String -Pattern "error" -CaseSensitive:$false
```

**Linux/macOS:**
```bash
docker compose logs

# Look for specific errors
docker compose logs | grep -i error
```

**Common issues:**
- Invalid `.env` syntax (no spaces around `=`)
- Missing required environment variables (`IS_SERVER`, `REMOTE_API_URL`, `REMOTE_API_KEY`)
- Docker Desktop not running (Windows)
- Port conflicts (shouldn't happen with stdio MCP)

### Tools Not Showing in LLM

**Checklist:**
1. Verify client is running: `docker compose ps`
2. Check client logs: `docker compose logs -f`
3. Verify LLM MCP configuration points to correct container name: `crawl4ai-rag-client`
4. Restart your LLM application (Claude Desktop, LM Studio)
5. Check LLM logs for MCP connection errors

**Claude Desktop (Windows):**
- Logs: `%APPDATA%\Claude\logs\`
- Config: `%APPDATA%\Claude\claude_desktop_config.json`

**Claude Desktop (macOS):**
- Logs: `~/Library/Logs/Claude/`
- Config: `~/Library/Application Support/Claude/claude_desktop_config.json`

### Container Name Mismatch

**Symptoms:** LLM can't connect to MCP server

**Verify container name:**
```bash
docker ps --filter "name=crawl4ai-rag-client"
```

**Should show:** Container named `crawl4ai-rag-client`

**Fix:** Ensure your LLM config uses the exact container name: `crawl4ai-rag-client`

## Updating Configuration

To apply changes to `.env`:

**Windows (PowerShell):**
```powershell
docker compose down
docker compose up -d
```

**Linux/macOS:**
```bash
docker compose down
docker compose up -d
```

## Network Requirements

The client needs outbound access to:
- Server URL on configured port (default: 8080)
- HTTPS if using secure connection

No inbound ports need to be opened (unless accessing from external LLM).

## Security Notes

- Keep `.env` file secure (contains API key)
- Use HTTPS for production deployments
- Don't share `REMOTE_API_KEY` publicly
- `BLOCKED_DOMAIN_KEYWORD` is only needed for admin operations

## Data Storage

The client doesn't store any data locally. All:
- Crawled content
- Embeddings
- Knowledge base data

...is stored on the remote server.

## Performance Notes

Client mode is lightweight:
- Minimal CPU usage (just forwarding requests)
- Low memory footprint (~100MB)
- No database storage needed
- Network latency depends on server connection

## Getting Help

For issues:
1. Check client logs: `docker compose logs -f`
2. Test server connection: `curl http://SERVER_URL/health`
3. Verify `.env` configuration matches server
4. Review `.env_template.txt` for detailed settings

## Advanced Configuration

See `.env_template.txt` for detailed documentation of all available settings including:
- Custom local MCP server port
- Logging levels
- Debug settings

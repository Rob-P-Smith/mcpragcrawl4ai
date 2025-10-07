# Client Deployment Setup Guide

This directory contains the configuration for deploying the lightweight Crawl4AI RAG MCP Client that connects to a remote server.

## What is Client Mode?

Client mode runs a lightweight MCP server that forwards all requests to a remote REST API server. Use this when:

- Your LLM runs on a different machine than the RAG server
- You want minimal resource usage on the client machine
- You need to connect to a centralized RAG knowledge base

```
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│     LLM     │ ◄─MCP─► │    Client    │ ◄─HTTP─►│    Server    │
│ (Claude/LM) │         │ (Forwarder)  │         │ (Full RAG)   │
└─────────────┘         └──────────────┘         └──────────────┘
```

## Quick Start

### 1. Get Server Details

Before setting up the client, you need from your server administrator:

- Server URL (e.g., `http://192.168.10.50:8080`)
- API Key (`REMOTE_API_KEY`)
- Blocked domain keyword (`BLOCKED_DOMAIN_KEYWORD`)

### 2. Create Environment File

```bash
# Copy the template
cp .env_template.txt .env

# Edit with your server details
nano .env  # or use your preferred editor
```

### 3. Configure Server Connection

Update these required settings in `.env`:

```bash
REMOTE_API_URL=http://YOUR_SERVER_IP:8080
REMOTE_API_KEY=your_api_key_from_server
BLOCKED_DOMAIN_KEYWORD=your_keyword_from_server
```

### 4. Test Server Connectivity

Before starting the client, verify you can reach the server:

```bash
# Test server connectivity
curl http://YOUR_SERVER_IP:8080/health

# Should return: {"status":"healthy","timestamp":"..."}
```

### 5. Start the Client

```bash
# Start the client
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

## Configure Your LLM

### Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

### LM Studio

Configure MCP connection:
- Server URL: `http://localhost:3000`
- Protocol: MCP over HTTP

## Available Tools

Once connected, your LLM will have access to:

### Content Retrieval
- **crawl_url**: Fetch and process a single URL
- **crawl_and_remember**: Crawl URL and store in knowledge base
- **deep_crawl**: Recursively crawl a website (with depth/page limits)

### Knowledge Base Management
- **ask**: Query the knowledge base using semantic search
- **list_memory**: List stored content
- **list_domains**: List unique domains in knowledge base
- **forget_url**: Remove specific content
- **clear_temp_memory**: Clear temporary session content
- **db_stats**: Get database statistics

### Domain Blocking (Admin)
- **add_blocked_domain**: Add domain pattern to blocklist
- **remove_blocked_domain**: Remove domain from blocklist (requires keyword)
- **list_blocked_domains**: View blocked domain patterns

## Troubleshooting

### Connection Refused

Check server connectivity:
```bash
# Test direct connection
curl http://YOUR_SERVER_IP:8080/health

# Check DNS resolution
ping YOUR_SERVER_IP

# Check firewall
telnet YOUR_SERVER_IP 8080
```

### Authentication Failed

Verify API key:
```bash
# Test with curl
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://YOUR_SERVER_IP:8080/health
```

If this fails, the API key is incorrect. Contact your server administrator.

### Client Container Won't Start

Check logs:
```bash
docker compose logs

# Look for specific errors
docker compose logs | grep -i error
```

Common issues:
- Invalid `.env` syntax
- Port 3000 already in use
- Missing required environment variables

### Tools Not Showing in LLM

1. Verify client is running: `docker compose ps`
2. Check client logs: `docker compose logs -f`
3. Restart your LLM application
4. Verify LLM MCP configuration is correct

## Updating Configuration

To apply changes to `.env`:

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

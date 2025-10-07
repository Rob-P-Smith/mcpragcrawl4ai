# Client Deployment

This deploys the Crawl4AI MCP client on your development laptop (WSL/Linux).

## What This Does

- Runs a lightweight Docker container with the MCP client
- Forwards all MCP calls to the remote API server (.env/SERVERIP:SERVERPORT)
- Keeps your local Python environment clean
- Easy start/stop with Docker commands

## Prerequisites

- Docker and docker-compose installed
- Network access to the server (.env/SERVERIP:SERVERPORT)

## Quick Setup

1. **Run setup script**:

   ```bash
   ./setup-client.sh
   ```

2. **Edit configuration**:

   ```bash
   # Update .env with your server details
   nano .env
   ```

3. **Restart if needed**:
   ```bash
   docker-compose restart
   ```

## Manual Setup

1. **Create .env file**:

   ```bash
   cp .env-template .env
   # Edit .env with correct SERVER-IP and API key
   ```

2. **Build and start**:
   ```bash
   docker-compose up -d
   ```

## Configuration

Edit `.env` file:

- `REMOTE_API_URL`: Your server URL (.env/SERVERIP:SERVERPORT)
- `REMOTE_API_KEY`: Same API key as server

## LM-Studio Configuration

Configure MCP server in LM-Studio:

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "crawl4ai-mcp-client",
        "python3",
        "core/rag_processor.py"
      ]
    }
  }
}
```

## Commands

- **Start**: `docker-compose up -d`
- **Stop**: `docker-compose down`
- **Logs**: `docker-compose logs -f`
- **Status**: `docker-compose ps`

## Troubleshooting

- **Connection refused**: Check server IP and port in .env
- **Authentication failed**: Verify API key matches server
- **Container not starting**: Check `docker-compose logs`

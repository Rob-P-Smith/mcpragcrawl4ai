# Deployment Guide

This guide covers deployment scenarios for the Crawl4AI RAG MCP Server.

> **Note**: For comprehensive deployment instructions including Docker server and client deployments, see the [Complete Deployment Guide](../deployments.md).

## Local Development Environment

### Prerequisites
- Ubuntu/Linux system or macOS
- Docker installed
- Python 3.8 or higher
- At least 4GB RAM available
- 10GB free disk space

### Setup Steps

1. **Clone the repository**:
```bash
git clone https://github.com/Rob-P-Smith/mcpragcrawl4ai.git
cd mcpragcrawl4ai
```

2. **Create and activate virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Start Crawl4AI service**:
```bash
docker run -d \
  --name crawl4ai \
  --network crawler_default \
  -p 11235:11235 \
  unclecode/crawl4ai:latest
```

5. **Configure environment**:
```bash
cat > .env << EOF
IS_SERVER=true
LOCAL_API_KEY=$(openssl rand -base64 32)
DB_PATH=./data/crawl4ai_rag.db
CRAWL4AI_URL=http://localhost:11235
EOF
```

6. **Run MCP server**:
```bash
python3 core/rag_processor.py
```

### LM-Studio Configuration (Local Development)

Update LM-Studio's MCP configuration:

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "/absolute/path/to/.venv/bin/python3",
      "args": ["/absolute/path/to/core/rag_processor.py"]
    }
  }
}
```

## Production Deployment Options

For production deployments, you have several options:

### 1. Docker Server Deployment
Deploy a full-featured server with REST API and MCP capabilities in Docker.

**Quick Start:**
```bash
docker compose -f deployments/server/docker-compose.yml up -d
```

See [Server Deployment Documentation](../../deployments/server/README.md) for details.

### 2. Docker Client Deployment
Deploy a lightweight MCP client that forwards requests to a remote server.

**Quick Start:**
```bash
docker compose -f deployments/client/docker-compose.yml up -d
```

See [Client Deployment Documentation](../../deployments/client/README.md) for details.

### 3. Complete Deployment Guide
For comprehensive deployment instructions, architecture diagrams, security considerations, and advanced configurations, see:

**[Complete Deployment Guide](../deployments.md)**

This includes:
- Server deployment (REST API + MCP)
- Client deployment (lightweight forwarder)
- Network configuration
- Security best practices
- Performance optimization
- Backup and recovery
- Monitoring and scaling

## Environment Variables

### Core Settings
- `IS_SERVER` - `true` for server mode, `false` for client mode (default: `true`)
- `SERVER_HOST` - Host to bind API server (default: `0.0.0.0`)
- `SERVER_PORT` - Port for API server (default: `8080`)

### Authentication
- `LOCAL_API_KEY` - API key for server mode
- `REMOTE_API_KEY` - API key for client mode
- `REMOTE_API_URL` - Remote server URL for client mode

### Database
- `DB_PATH` - SQLite database path (default: `crawl4ai_rag.db`)

### Services
- `CRAWL4AI_URL` - Crawl4AI service URL (default: `http://localhost:11235`)

### Security
- `RATE_LIMIT_PER_MINUTE` - API rate limit (default: `60`)

## Common Commands

### Development
```bash
# Run MCP server
python3 core/rag_processor.py

# Run REST API server
python3 deployments/server/start_api_server.py

# Run tests
python3 core/utilities/test_sqlite_vec.py
python3 core/utilities/dbstats.py
```

### Docker Operations
```bash
# Server deployment
docker compose -f deployments/server/docker-compose.yml up -d
docker compose -f deployments/server/docker-compose.yml logs -f
docker compose -f deployments/server/docker-compose.yml down

# Client deployment
docker compose -f deployments/client/docker-compose.yml up -d
docker compose -f deployments/client/docker-compose.yml logs -f
docker compose -f deployments/client/docker-compose.yml down
```

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Check what's using the port
sudo lsof -i :8080
sudo lsof -i :11235

# Kill the process if safe
sudo kill -9 <PID>
```

**Database errors:**
```bash
# Check database permissions
ls -la data/crawl4ai_rag.db

# Verify database integrity
sqlite3 data/crawl4ai_rag.db "PRAGMA integrity_check;"
```

**Crawl4AI connection failed:**
```bash
# Check if Crawl4AI is running
docker ps | grep crawl4ai

# Check Crawl4AI logs
docker logs crawl4ai

# Restart Crawl4AI
docker restart crawl4ai
```

For more troubleshooting, see:
- [Troubleshooting Guide](troubleshooting.md)
- [Complete Deployment Guide](../deployments.md#troubleshooting)

## Next Steps

- [Quick Start Guide](quick-start.md) - Get started quickly
- [API Documentation](../API_README.md) - REST API reference
- [Complete Deployment Guide](../deployments.md) - Advanced deployment options
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

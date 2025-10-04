# Deployment Guide

Complete guide for deploying the Crawl4AI RAG MCP Server in different configurations.

## Overview

This system supports multiple deployment scenarios:

1. **Local Development** - Running directly on your machine with Python virtual environment
2. **Server Deployment** - Docker-based deployment hosting REST API + MCP server
3. **Client Deployment** - Lightweight Docker client forwarding to remote server

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Crawl4AI Service                      │
│                   (Port 11235)                           │
│              Docker: unclecode/crawl4ai                  │
└─────────────────────────────────────────────────────────┘
                            ▲
                            │
┌───────────────────────────┼─────────────────────────────┐
│                  Server Deployment                       │
│                                                          │
│  ┌────────────────┐          ┌───────────────────┐     │
│  │   REST API     │          │   MCP Server      │     │
│  │  (Port 8080)   │          │   (Port 3000)     │     │
│  │   FastAPI      │          │  stdio over TCP   │     │
│  └────────────────┘          └───────────────────┘     │
│           │                           │                 │
│           └───────────┬───────────────┘                 │
│                       ▼                                 │
│              SQLite + Vector DB                         │
│           (Shared volume: ./data)                       │
└─────────────────────────────────────────────────────────┘
```

## Deployment Option 1: Server Deployment

Deploy a full-featured server with REST API and MCP server capabilities.

### What You Get

- **REST API** on port 8080 for HTTP clients
- **MCP Server** on port 3000 for LM-Studio integration
- **Full RAG capabilities** with local vector database
- **Supervisord** managing both services in one container

### Prerequisites

- Docker and Docker Compose v2 installed
- Crawl4AI container running on `crawler_default` network
- Ports 8080 and 3000 available
- At least 4GB RAM and 10GB disk space

### Configuration

Create or edit `deployments/server/.env`:

```bash
# Server Configuration
IS_SERVER=true
SERVER_HOST=0.0.0.0
SERVER_PORT=8080

# Authentication (CHANGE THIS!)
LOCAL_API_KEY=your-secure-api-key-here

# Database Configuration
DB_PATH=/app/data/crawl4ai_rag.db

# Crawl4AI Service (Docker network)
CRAWL4AI_URL=http://crawl4ai:11235

# Security Settings
ENABLE_CORS=true
MAX_REQUEST_SIZE=10485760
RATE_LIMIT_PER_MINUTE=60

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/data/crawl4ai_rag_api.log
```

**Generate a secure API key:**
```bash
openssl rand -base64 32
```

### Deployment Steps

1. **Ensure Crawl4AI is running**:
```bash
# Check if Crawl4AI container exists
docker ps | grep crawl4ai

# If not running, start it
docker run -d \
  --name crawl4ai \
  --network crawler_default \
  -p 11235:11235 \
  unclecode/crawl4ai:latest
```

2. **Build and start the server**:
```bash
# From project root
docker compose -f deployments/server/docker-compose.yml build
docker compose -f deployments/server/docker-compose.yml up -d
```

3. **Verify deployment**:
```bash
# Check container status
docker compose -f deployments/server/docker-compose.yml ps

# Test REST API
curl http://localhost:8080/health

# Test with API key
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8080/api/v1/status
```

### LM-Studio Configuration (Server Mode)

Configure LM-Studio to connect to the MCP server via TCP:

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
- Install socat: `sudo apt-get install socat` (Linux) or `brew install socat` (Mac)
- Ensure port 3000 is accessible

### Management Commands

```bash
# View logs
docker compose -f deployments/server/docker-compose.yml logs -f

# Restart services
docker compose -f deployments/server/docker-compose.yml restart

# Stop services
docker compose -f deployments/server/docker-compose.yml down

# Rebuild after code changes
docker compose -f deployments/server/docker-compose.yml build
docker compose -f deployments/server/docker-compose.yml up -d
```

## Deployment Option 2: Client Deployment

Deploy a lightweight client that forwards all requests to a remote server.

### What You Get

- **Minimal container** with no ML dependencies
- **MCP protocol** on stdin/stdout
- **API forwarding** to remote REST server
- **Clean local setup** without local database

### Prerequisites

- Docker and Docker Compose installed
- Network access to remote server
- Remote server credentials (API URL and key)

### Configuration

Create or edit `deployments/client/.env`:

```bash
# Client Mode
IS_SERVER=false

# Remote Server Configuration
REMOTE_API_URL=https://your-server.com:8080
REMOTE_API_KEY=your-remote-api-key-here
```

### Deployment Steps

1. **Configure environment**:
```bash
cd deployments/client
cp .env-template .env
nano .env  # Update with your server details
```

2. **Build and start client**:
```bash
# From project root
docker compose -f deployments/client/docker-compose.yml build
docker compose -f deployments/client/docker-compose.yml up -d
```

3. **Verify deployment**:
```bash
# Check container status
docker compose -f deployments/client/docker-compose.yml ps

# Test connection (should wait for JSON-RPC input)
docker exec -i crawl4ai-mcp-client python3 core/rag_processor.py
```

### LM-Studio Configuration (Client Mode)

Configure LM-Studio to use the Docker client:

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

### Management Commands

```bash
# View logs
docker compose -f deployments/client/docker-compose.yml logs -f

# Restart client
docker compose -f deployments/client/docker-compose.yml restart

# Stop client
docker compose -f deployments/client/docker-compose.yml down
```

## Deployment Option 3: Local Development

Run the system directly on your machine for development.

### Prerequisites

- Python 3.8 or higher
- Virtual environment
- Crawl4AI running (Docker or local)

### Setup Steps

1. **Create virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment**:
```bash
# Create .env file in project root
cat > .env << EOF
IS_SERVER=true
LOCAL_API_KEY=dev-api-key
DB_PATH=./data/crawl4ai_rag.db
CRAWL4AI_URL=http://localhost:11235
EOF
```

4. **Start Crawl4AI** (if not running):
```bash
docker run -d \
  --name crawl4ai \
  -p 11235:11235 \
  unclecode/crawl4ai:latest
```

5. **Run the MCP server**:
```bash
# For MCP stdio mode (LM-Studio)
python3 core/rag_processor.py

# For REST API mode
python3 deployments/server/start_api_server.py
```

### LM-Studio Configuration (Local Development)

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "/path/to/your/.venv/bin/python3",
      "args": ["/path/to/your/core/rag_processor.py"],
      "env": {
        "PYTHONPATH": "/path/to/your/project"
      }
    }
  }
}
```

## Network Configuration

### Docker Networks

The server deployment uses the external `crawler_default` network:

```bash
# Check if network exists
docker network ls | grep crawler_default

# Create network if needed
docker network create crawler_default

# Inspect network
docker network inspect crawler_default
```

### Port Mappings

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Crawl4AI | 11235 | HTTP | Web crawling service |
| REST API | 8080 | HTTP | REST endpoints |
| MCP Server | 3000 | TCP | MCP stdio over TCP (with socat) |

## Environment Variables Reference

### Core Settings
- `IS_SERVER` - `true` for server mode, `false` for client mode
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
- `ENABLE_CORS` - Enable CORS (default: `true`)
- `MAX_REQUEST_SIZE` - Max request size in bytes (default: `10485760`)
- `RATE_LIMIT_PER_MINUTE` - API rate limit (default: `60`)

### Logging
- `LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: `INFO`)
- `LOG_FILE` - Log file path (default: console only)

## Troubleshooting

### Server Deployment Issues

**Container won't start:**
```bash
docker compose -f deployments/server/docker-compose.yml logs
```

**Can't connect to Crawl4AI:**
```bash
# Check if both containers are on same network
docker network inspect crawler_default

# Test connection from API container
docker exec -it crawl4ai-rag-server curl http://crawl4ai:11235/
```

**Database errors:**
```bash
# Check database file permissions
ls -la data/crawl4ai_rag.db

# Verify database is accessible
docker exec -it crawl4ai-rag-server sqlite3 /app/data/crawl4ai_rag.db ".tables"
```

### Client Deployment Issues

**Connection refused:**
- Verify `REMOTE_API_URL` in `.env`
- Check firewall rules on server
- Test with curl: `curl -H "Authorization: Bearer API_KEY" https://server:8080/health`

**Authentication failed:**
- Ensure `REMOTE_API_KEY` matches server's `LOCAL_API_KEY`
- Check for typos in API key

### LM-Studio Issues

**MCP server not found:**
- Verify absolute paths in mcp.json
- Restart LM-Studio after configuration changes
- Check LM-Studio logs for connection errors

**socat not found:**
```bash
# Install socat
sudo apt-get install socat  # Linux
brew install socat          # Mac
```

## Security Considerations

### API Keys
1. **Never use default keys** - Generate strong, random keys
2. **Rotate regularly** - Change keys every 90 days
3. **Store securely** - Use environment variables or secrets manager
4. **Different keys per environment** - Dev, staging, production

### Network Security
1. **Use HTTPS in production** - Deploy behind reverse proxy with TLS
2. **Restrict access** - Configure firewall rules
3. **Private networks** - Use VPN for remote access
4. **Rate limiting** - Adjust `RATE_LIMIT_PER_MINUTE` as needed

### Database Security
1. **Regular backups** - Automated daily backups
2. **File permissions** - Restrict database file access
3. **Encryption at rest** - Consider disk encryption
4. **Access logs** - Monitor database queries

## Performance Optimization

### Resource Allocation
```bash
# Monitor resource usage
docker stats crawl4ai-rag-server

# Adjust container resources in docker-compose.yml
services:
  crawl4ai-rag:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          memory: 2G
```

### Database Optimization
```bash
# Run VACUUM to optimize database
docker exec -it crawl4ai-rag-server \
  sqlite3 /app/data/crawl4ai_rag.db "VACUUM;"

# Check database size
docker exec -it crawl4ai-rag-server \
  ls -lh /app/data/crawl4ai_rag.db
```

### Caching
- Enable response caching for frequently accessed content
- Use Redis for distributed caching (optional)

## Backup and Recovery

### Database Backup
```bash
# Manual backup
docker exec crawl4ai-rag-server \
  sqlite3 /app/data/crawl4ai_rag.db ".backup /app/data/backup.db"

# Copy to host
docker cp crawl4ai-rag-server:/app/data/backup.db ./backups/

# Automated backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker exec crawl4ai-rag-server \
  sqlite3 /app/data/crawl4ai_rag.db ".backup /app/data/backup_$DATE.db"
docker cp crawl4ai-rag-server:/app/data/backup_$DATE.db ./backups/
```

### Restore from Backup
```bash
# Stop the server
docker compose -f deployments/server/docker-compose.yml down

# Replace database
cp ./backups/backup_YYYYMMDD_HHMMSS.db ./data/crawl4ai_rag.db

# Restart server
docker compose -f deployments/server/docker-compose.yml up -d
```

## Monitoring

### Health Checks
```bash
# REST API health
curl http://localhost:8080/health

# Detailed status (requires API key)
curl -H "Authorization: Bearer API_KEY" \
  http://localhost:8080/api/v1/status
```

### Logging
```bash
# Follow all logs
docker compose -f deployments/server/docker-compose.yml logs -f

# Follow specific service logs
docker logs -f crawl4ai-rag-server

# Application error log
tail -f data/crawl4ai_rag_errors.log
```

### Metrics (Optional)
- Integrate Prometheus for metrics collection
- Use Grafana for visualization
- Monitor API response times, error rates, database size

## Scaling

### Horizontal Scaling
- Deploy multiple server instances behind load balancer
- Use shared database or database replication
- Session affinity for temporary content

### Vertical Scaling
- Increase container resources (CPU, memory)
- Optimize database queries and indexes
- Use connection pooling

### Load Balancing Example (nginx)
```nginx
upstream crawl4ai_backend {
    server 192.168.1.10:8080;
    server 192.168.1.11:8080;
    server 192.168.1.12:8080;
}

server {
    listen 443 ssl;
    server_name api.example.com;

    location / {
        proxy_pass http://crawl4ai_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

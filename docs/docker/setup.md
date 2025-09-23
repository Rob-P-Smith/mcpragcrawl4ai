# Docker Setup Instructions

This document provides detailed instructions for setting up the RAG system using Docker containers.

## Prerequisites

- Docker and docker-compose installed
- At least 4GB RAM available
- 10GB free disk space

## Configuration Files

### docker-compose.yml
```yaml
version: '3.8'
services:
  crawl4ai:
    image: unclecode/crawl4ai:latest
    container_name: crawl4ai
    ports:
      - "11235:11235"
    shm_size: '1gb'
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11235/"]
      interval: 30s
      timeout: 10s
      retries: 3
    environment:
      - LOG_LEVEL=INFO

  crawl4ai-mcp-server:
    build: .
    container_name: crawl4ai-mcp-server
    ports:
      - "8765:8765"
    volumes:
      - ./data:/app/data
    depends_on:
      - crawl4ai
```

### .env (Optional)
```bash
# API Configuration
IS_SERVER=true
LOCAL_API_KEY=your-secure-api-key-here

# Database Configuration
DB_PATH=/app/data/crawl4ai_rag.db

# Crawl4AI Service URL
CRAWL4AI_URL=http://localhost:11235

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
```

## Build and Deployment Steps

### 1. Build the Docker Image

```bash
docker build -t crawl4ai-mcp-server:latest .
```

This command builds a custom Docker image with all required Python dependencies.

### 2. Start the Services

```bash
docker compose up -d
```

The `-d` flag runs the containers in detached mode (in the background).

### 3. Verify Services are Running

```bash
docker compose ps
```

You should see both `crawl4ai` and `crawl4ai-mcp-server` containers with status "Up".

## Environment Variables

The following environment variables can be configured:

### Core Settings
- `IS_SERVER`: `true` for server mode, `false` for client mode
- `SERVER_HOST`: Host to bind API server (default: `0.0.0.0`)
- `SERVER_PORT`: Port for API server (default: `8765`)

### Authentication
- `LOCAL_API_KEY`: API key for server mode authentication
- `REMOTE_API_KEY`: API key for client mode remote requests
- `REMOTE_API_URL`: Remote server URL for client mode

### System Configuration
- `DB_PATH`: SQLite database path (default: `/app/data/crawl4ai_rag.db`)
- `CRAWL4AI_URL`: Crawl4AI service URL (default: `http://localhost:11235`)
- `RATE_LIMIT_PER_MINUTE`: API rate limit (default: `60`)

## Service-Specific Configuration

### Crawl4AI Container
The Crawl4AI container runs the official Crawl4AI Docker image and handles web content extraction.

**Ports**: 
- 11235: Web interface for crawling operations

**Environment Variables**:
- `LOG_LEVEL`: Logging level (INFO, DEBUG, WARNING, ERROR)

### MCP Server + MCPO Container
The custom-built container runs the Python-based RAG server with REST API endpoints and OpenWebUI integration.

**Ports**:
- 8765: REST API endpoint for OpenWebUI

**Volumes**:
- `./data:/app/data`: Persists database files on the host system

## Remote Access Configuration

### OpenWebUI Integration

To connect OpenWebUI to this setup:

1. **Access URL**: `http://your-server-ip:8765/openapi.json`
2. **In OpenWebUI**: Add Connection → OpenAPI
3. **Configuration**:
   - URL: `http://your-server-ip:8765`
   - Auth: Session (no API key required)
   - Name: Any descriptive name

### Available Endpoints

Once connected, OpenWebUI will have access to all MCP tools via REST API:
- `/crawl_url` - Crawl without storing
- `/crawl_and_remember` - Crawl and store permanently  
- `/crawl_temp` - Crawl and store temporarily
- `/deep_crawl_dfs` - Deep crawl without storing
- `/deep_crawl_and_store` - Deep crawl and store all pages
- `/search_memory` - Semantic search of stored content
- `/list_memory` - List stored content
- `/forget_url` - Remove specific content
- `/clear_temp_memory` - Clear temporary content

## Batch Crawling

### Running the Batch Crawler

To crawl all domains from `domains.txt`:

```bash
docker exec -it crawl4ai-mcp-server python3 batch_crawler.py
```

### Batch Crawler Features

- **Sequential Processing**: Crawls each domain one at a time to avoid overwhelming the system
- **Deep Crawling**: Uses depth 4, up to 250 pages per domain
- **Permanent Storage**: All content stored with 'permanent' retention policy
- **Domain Tagging**: Each domain gets tagged as 'batch_crawl,domain_N'
- **Same Database**: Uses the same SQLite database as the MCP server
- **Progress Tracking**: Shows completion status for each domain

### Pre-configured Domains

The `domains.txt` includes documentation sites for:
- Node.js, npm, ESLint, TSConfig
- .NET 8 Entity Framework
- Axios, Vite
- Crawl4AI, LM Studio
- And more...

## Monitoring and Maintenance

### Check Service Status

```bash
docker compose ps
```

### View Logs

```bash
# View all logs
docker compose logs

# Follow logs in real-time
docker compose logs -f

# View specific service logs
docker compose logs crawl4ai
docker compose logs crawl4ai-mcp-server
```

### Check Database Statistics

```bash
docker exec -it crawl4ai-mcp-server python3 dbstats.py
```

### Direct Database Access

```bash
# Access SQLite database directly
docker exec -it crawl4ai-mcp-server sqlite3 /app/data/crawl4ai_rag.db

# Example queries
.tables
SELECT COUNT(*) FROM crawled_content;
SELECT url, title, timestamp FROM crawled_content LIMIT 5;
```

## Troubleshooting

### Common Issues

**Container not starting:**
```bash
docker compose logs crawl4ai
docker compose logs crawl4ai-mcp-server
```

**Python import errors:**
```bash
# Check installed packages
docker exec -it crawl4ai-mcp-server pip list | grep -E "(sentence|sqlite|numpy|requests)"
```

**MCP connection issues:**
- Verify file paths in configuration files are correct
- Ensure script has execute permissions

**Memory issues:**
- Increase Docker container memory if needed
- Monitor system RAM usage during model loading

### Log Files

**Error logs:** `./data/crawl4ai_rag_errors.log`
**Docker logs:** `docker compose logs crawl4ai` and `docker compose logs crawl4ai-mcp-server`

## Production Considerations

1. **Use HTTPS**: Configure TLS certificates for production
2. **Secure API Keys**: Use strong, randomly generated keys
3. **Database Backup**: Regular backups of the data directory
4. **Monitoring**: Add Prometheus metrics and health checks
5. **Load Balancing**: Use nginx or similar for production load balancing

# Crawl4AI RAG API - Bidirectional MCP Communication

This implementation adds a REST API layer that enables bidirectional communication between local MCP servers and remote deployments. The system can operate in two modes:

- **Server Mode**: Hosts REST API endpoints for remote clients
- **Client Mode**: Forwards MCP tool calls to a remote REST API server

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy and edit the `.env` file:

```bash
# For Server Mode (hosting the API)
IS_SERVER=true
LOCAL_API_KEY=your-secure-api-key-here

# For Client Mode (forwarding to remote)
IS_SERVER=false
REMOTE_API_URL=https://your-server.com:8080
REMOTE_API_KEY=your-remote-api-key-here
```

### 3. Run in Server Mode

```bash
# Option 1: Using the startup script
python3 start_api_server.py

# Option 2: Using uvicorn directly
uvicorn api.api:create_app --host 0.0.0.0 --port 8080
```

### 4. Run in Client Mode

```bash
# The existing MCP server automatically detects client mode
python3 core/rag_processor.py
```

## Configuration Variables

### Core Settings
- `IS_SERVER`: `true` for server mode, `false` for client mode
- `SERVER_HOST`: Host to bind API server (default: `0.0.0.0`)
- `SERVER_PORT`: Port for API server (default: `8080`)

### Authentication
- `LOCAL_API_KEY`: API key for server mode authentication
- `REMOTE_API_KEY`: API key for client mode remote requests
- `REMOTE_API_URL`: Remote server URL for client mode

### System Configuration
- `DB_PATH`: SQLite database path (default: `crawl4ai_rag.db`)
- `CRAWL4AI_URL`: Crawl4AI service URL (default: `http://localhost:11235`)
- `RATE_LIMIT_PER_MINUTE`: API rate limit (default: `60`)

## REST API Endpoints

### Crawling Endpoints

#### POST /api/v1/crawl
Crawl a URL without storing the content.

```bash
curl -X POST "http://localhost:8080/api/v1/crawl" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

#### POST /api/v1/crawl/store
Crawl and store content permanently.

```bash
curl -X POST "http://localhost:8080/api/v1/crawl/store" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "tags": "example,documentation",
    "retention_policy": "permanent"
  }'
```

#### POST /api/v1/crawl/temp
Crawl and store content temporarily (session only).

#### POST /api/v1/crawl/deep
Deep crawl multiple pages without storing.

```bash
curl -X POST "http://localhost:8080/api/v1/crawl/deep" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://docs.example.com",
    "max_depth": 3,
    "max_pages": 50,
    "include_external": false
  }'
```

#### POST /api/v1/crawl/deep/store
Deep crawl and store all discovered pages.

### Knowledge Base Endpoints

#### POST /api/v1/search
Search stored knowledge using semantic similarity.

```bash
curl -X POST "http://localhost:8080/api/v1/search" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning algorithms",
    "limit": 10
  }'
```

#### GET /api/v1/memory
List all stored content.

```bash
curl -X GET "http://localhost:8080/api/v1/memory?filter=permanent" \
  -H "Authorization: Bearer your-api-key"
```

#### DELETE /api/v1/memory
Remove specific content by URL.

```bash
curl -X DELETE "http://localhost:8080/api/v1/memory" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

#### DELETE /api/v1/memory/temp
Clear all temporary content.

### System Endpoints

#### GET /api/v1/status
Get system status and health information.

#### GET /health
Basic health check endpoint.

## Architecture

### Server Mode Flow
1. Client sends HTTP request with API key
2. Authentication middleware validates API key
3. Request routed to appropriate handler
4. Handler calls existing crawler/storage functions
5. Response returned as JSON

### Client Mode Flow
1. LLM sends MCP tool call to local processor
2. Processor detects client mode from environment
3. MCP request transformed to REST API format
4. HTTP request sent to remote server with API key
5. API response transformed back to MCP format
6. Response returned to LLM

## Security Features

- **API Key Authentication**: Bearer token authentication for all endpoints
- **Rate Limiting**: Configurable requests per minute per API key
- **Input Validation**: Pydantic models for request validation
- **URL Validation**: Prevents access to internal/private networks
- **HTTPS Support**: Configurable CORS and security headers
- **Session Management**: Automatic cleanup of expired sessions

## Deployment

### Docker Compose

```yaml
version: '3.8'
services:
  crawl4ai-rag-api:
    build: .
    ports:
      - "8080:8080"
    environment:
      - IS_SERVER=true
      - LOCAL_API_KEY=your-secure-key
      - DB_PATH=/app/data/crawl4ai_rag.db
    volumes:
      - ./data:/app/data
    depends_on:
      - crawl4ai
```

### Production Considerations

1. **Use HTTPS**: Configure TLS certificates
2. **Secure API Keys**: Use strong, randomly generated keys
3. **Database Backup**: Regular backups of SQLite database
4. **Monitoring**: Add Prometheus metrics and health checks
5. **Load Balancing**: Use nginx or similar for production load balancing

## Development

### Testing

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Code formatting
black api/ core/ operations/ data/

# Linting
flake8 api/ core/ operations/ data/
```

### API Documentation

When the server is running, visit:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

## Troubleshooting

### Common Issues

**API Key Authentication Fails**
- Verify `LOCAL_API_KEY` is set in `.env`
- Ensure `Authorization: Bearer <key>` header is included

**Client Mode Connection Fails**
- Check `REMOTE_API_URL` and `REMOTE_API_KEY` in `.env`
- Verify remote server is accessible
- Test with curl directly to remote API

**Database Errors**
- Ensure SQLite database is writable
- Check disk space and permissions
- Verify sqlite-vec extension is properly installed

**Rate Limiting**
- Check `RATE_LIMIT_PER_MINUTE` setting
- Wait before retrying requests
- Consider increasing rate limit for your use case

### Logging

API requests are logged to:
- Console output (development)
- `crawl4ai_api.log` (if configured)
- `crawl4ai_rag_errors.log` (errors only)

## Migration from MCP-only

Existing MCP clients continue to work without changes:

1. **No Changes Required**: Existing `core/rag_processor.py` usage unchanged
2. **Automatic Detection**: Client mode detected from `.env` configuration
3. **Backward Compatible**: MCP protocol remains identical to clients
4. **Gradual Migration**: Can enable API access while maintaining MCP functionality
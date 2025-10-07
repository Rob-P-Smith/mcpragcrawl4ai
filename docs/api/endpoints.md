# API Endpoints

This document provides comprehensive documentation for all REST API endpoints in the Crawl4AI RAG MCP Server.

## Base URL

```
http://localhost:8080
```

## Authentication

All API endpoints (except `/health`) require authentication using a Bearer token:

```http
Authorization: Bearer your-api-key-here
```

The API key is configured via environment variables:
- `LOCAL_API_KEY`: For server mode
- `REMOTE_API_KEY`: For client mode

## System Endpoints

### GET /health

Basic health check endpoint (no authentication required).

**Request:**
```http
GET /health HTTP/1.1
Host: localhost:8080
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### GET /api/v1/status

Get comprehensive system status and component health.

**Request:**
```http
GET /api/v1/status HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Response:**
```json
{
  "success": true,
  "status": "operational",
  "components": {
    "database": "healthy",
    "crawl4ai": "healthy",
    "session": "abc123-session-id"
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### GET /api/v1/help

Get comprehensive help documentation for all available tools.

**Request:**
```http
GET /api/v1/help HTTP/1.1
Host: localhost:8080
```

**Response:**
```json
{
  "success": true,
  "tools": [
    {
      "name": "crawl_url",
      "example": "Crawl http://www.example.com without storing",
      "parameters": "url: string"
    },
    ...
  ],
  "api_info": {
    "base_url": "/api/v1",
    "authentication": "Bearer token required in Authorization header",
    "formats": {
      "retention_policy": ["permanent", "session_only", "30_days"],
      "http_methods": { ... }
    }
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

## Crawling Endpoints

### POST /api/v1/crawl

Crawl a URL without storing the content.

**Request:**
```http
POST /api/v1/crawl HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json

{
  "url": "https://example.com"
}
```

**Parameters:**
- `url` (string, required): URL to crawl

**Response:**
```json
{
  "success": true,
  "data": {
    "url": "https://example.com",
    "title": "Example Domain",
    "content": "Full page content...",
    "markdown": "# Example Domain\n\nContent in markdown...",
    "crawl_time": 2.34
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### POST /api/v1/crawl/store

Crawl a URL and store it permanently in the knowledge base.

**Request:**
```http
POST /api/v1/crawl/store HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json

{
  "url": "https://example.com",
  "tags": "example,documentation",
  "retention_policy": "permanent"
}
```

**Parameters:**
- `url` (string, required): URL to crawl
- `tags` (string, optional): Comma-separated tags for organization
- `retention_policy` (string, optional): Storage policy ('permanent', 'session_only', '30_days'). Default: 'permanent'

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "content_id": 12345,
    "url": "https://example.com",
    "title": "Example Domain",
    "stored": true,
    "embeddings_created": true
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### POST /api/v1/crawl/temp

Crawl a URL and store it temporarily (session only).

**Request:**
```http
POST /api/v1/crawl/temp HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json

{
  "url": "https://example.com",
  "tags": "temporary,testing"
}
```

**Parameters:**
- `url` (string, required): URL to crawl
- `tags` (string, optional): Comma-separated tags for organization

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "content_id": 12346,
    "url": "https://example.com",
    "retention_policy": "session_only",
    "stored": true
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### POST /api/v1/crawl/deep/store

Deep crawl multiple pages using DFS strategy and store all discovered pages.

**Request:**
```http
POST /api/v1/crawl/deep/store HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json

{
  "url": "https://docs.example.com",
  "max_depth": 3,
  "max_pages": 50,
  "retention_policy": "permanent",
  "tags": "deep_crawl,documentation",
  "include_external": false,
  "score_threshold": 0.0,
  "timeout": 600
}
```

**Parameters:**
- `url` (string, required): Starting URL for deep crawl
- `max_depth` (integer, optional): Maximum depth to crawl (1-5, default: 2)
- `max_pages` (integer, optional): Maximum pages to crawl (1-250, default: 10)
- `retention_policy` (string, optional): Storage policy (default: 'permanent')
- `tags` (string, optional): Tags for organization (auto-adds 'deep_crawl')
- `include_external` (boolean, optional): Follow external domain links (default: false)
- `score_threshold` (number, optional): Minimum URL score (0.0-1.0, default: 0.0)
- `timeout` (integer, optional): Maximum crawl time in seconds (60-1800)

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "pages_crawled": 48,
    "pages_stored": 45,
    "failed_pages": 3,
    "crawl_depth_reached": 3,
    "crawl_time": 125.5,
    "stored_pages": [
      {
        "url": "https://docs.example.com/page1",
        "content_id": 12347,
        "depth": 1
      },
      ...
    ],
    "failed_urls": [
      {
        "url": "https://docs.example.com/broken",
        "error": "404 Not Found"
      }
    ]
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

## Search Endpoints

### POST /api/v1/search

Search stored knowledge using semantic similarity.

**Request:**
```http
POST /api/v1/search HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json

{
  "query": "machine learning algorithms",
  "limit": 10,
  "tags": "ml,algorithms"
}
```

**Parameters:**
- `query` (string, required): Search query text
- `limit` (integer, optional): Number of results (default: 5, max: 1000)
- `tags` (string, optional): Comma-separated tags to filter by (ANY match)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "url": "https://docs.example.com/ml-algorithms",
      "title": "Machine Learning Algorithms Guide",
      "content": "This guide covers various machine learning algorithms...",
      "timestamp": "2024-01-15T14:30:00Z",
      "tags": "ml,algorithms,guide",
      "similarity_score": 0.92
    },
    ...
  ],
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### POST /api/v1/search/target

Intelligent search that discovers tags from initial results and expands search.

**Request:**
```http
POST /api/v1/search/target HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json

{
  "query": "react hooks",
  "initial_limit": 5,
  "expanded_limit": 20
}
```

**Parameters:**
- `query` (string, required): Search query for tag discovery
- `initial_limit` (integer, optional): Initial results for tag discovery (1-100, default: 5)
- `expanded_limit` (integer, optional): Maximum expanded results (1-1000, default: 20)

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "query": "react hooks",
    "results": [
      {
        "url": "https://example.com/react-hooks-guide",
        "title": "React Hooks Complete Guide",
        "content": "...",
        "similarity_score": 0.95
      },
      ...
    ],
    "discovered_tags": ["react", "hooks", "javascript", "frontend"],
    "expansion_used": true,
    "initial_results_count": 5,
    "expanded_results_count": 18
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

## Knowledge Base Management

### GET /api/v1/memory

List stored content in the knowledge base.

**Request:**
```http
GET /api/v1/memory?filter=permanent&limit=100 HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Parameters:**
- `filter` (string, optional): Filter by retention policy ('permanent', 'session_only', '30_days')
- `limit` (integer, optional): Maximum results to return (default: 100, max: 1000)

**Response:**
```json
{
  "success": true,
  "data": {
    "content": [
      {
        "url": "https://example.com/page1",
        "title": "Page Title",
        "timestamp": "2024-01-15T14:30:00Z",
        "retention_policy": "permanent",
        "tags": "example,docs"
      },
      ...
    ],
    "count": 50,
    "total_count": 1250,
    "limited": true,
    "limit": 100
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### DELETE /api/v1/memory

Remove specific content by URL from the knowledge base.

**Request:**
```http
DELETE /api/v1/memory?url=https://example.com HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Parameters:**
- `url` (string, required): URL to remove

**Response:**
```json
{
  "success": true,
  "data": {
    "removed_count": 1,
    "attempted_urls": [
      "https://example.com",
      "https://www.example.com"
    ],
    "original_url": "https://example.com"
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### DELETE /api/v1/memory/temp

Clear all temporary content from the current session.

**Request:**
```http
DELETE /api/v1/memory/temp HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Response:**
```json
{
  "success": true,
  "data": {
    "removed_count": 5,
    "session_id": "abc123-session-id"
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

## Database Statistics

### GET /api/v1/stats

Get comprehensive database statistics including record counts, storage size, and recent activity.

**Request:**
```http
GET /api/v1/stats HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "using_ram_db": true,
    "database_path": "/app/data/crawl4ai_rag.db",
    "total_pages": 1250,
    "vector_embeddings": 45678,
    "sessions": 12,
    "database_size_mb": 45.23,
    "database_size_bytes": 47423488,
    "retention_breakdown": {
      "permanent": 1100,
      "session_only": 120,
      "30_days": 30
    },
    "recent_activity": [
      {
        "url": "https://example.com/recent",
        "title": "Recent Page",
        "timestamp": "2024-01-15T14:25:00Z",
        "size_kb": 123.4,
        "retention_policy": "permanent"
      },
      ...
    ],
    "storage_breakdown": {
      "content_mb": 30.5,
      "embeddings_mb": 12.8,
      "metadata_mb": 1.93
    },
    "top_tags": [
      {"tag": "documentation", "count": 450},
      {"tag": "tutorial", "count": 320},
      ...
    ],
    "vec_extension_available": true
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### GET /api/v1/db/stats

Get RAM database sync statistics and health metrics.

**Request:**
```http
GET /api/v1/db/stats HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Response:**
```json
{
  "success": true,
  "mode": "memory",
  "disk_db_path": "/app/data/crawl4ai_rag.db",
  "disk_db_size_mb": 45.23,
  "sync_metrics": {
    "total_syncs": 127,
    "last_sync_time": 1705329000.0,
    "last_sync_duration": 0.15,
    "total_records_synced": 3456,
    "failed_syncs": 0,
    "pending_changes": 0
  },
  "health": {
    "pending_changes": 0,
    "last_sync_ago_seconds": 12.5,
    "sync_success_rate": 1.0
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### GET /api/v1/domains

List all unique domains stored in the knowledge base with page counts.

**Request:**
```http
GET /api/v1/domains HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "domains": [
      {"domain": "docs.python.org", "page_count": 245},
      {"domain": "github.com", "page_count": 189},
      {"domain": "example.com", "page_count": 156},
      ...
    ],
    "total_domains": 42,
    "total_pages": 1250
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

## Domain Blocking

### GET /api/v1/blocked-domains

List all blocked domain patterns.

**Request:**
```http
GET /api/v1/blocked-domains HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "blocked_domains": [
      {
        "pattern": "*.ru",
        "description": "Block all Russian domains",
        "created_at": "2024-01-01T00:00:00Z"
      },
      {
        "pattern": "*porn*",
        "description": "Block URLs containing 'porn'",
        "created_at": "2024-01-01T00:00:00Z"
      },
      ...
    ],
    "count": 6
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### POST /api/v1/blocked-domains

Add a domain pattern to the blocklist.

**Request:**
```http
POST /api/v1/blocked-domains HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json

{
  "pattern": "*.spam-site.com",
  "description": "Known spam domain"
}
```

**Parameters:**
- `pattern` (string, required): Domain pattern to block (supports wildcards)
  - `*.ru` - Block all .ru domains
  - `*spam*` - Block URLs containing 'spam'
  - `example.com` - Block exact domain
- `description` (string, optional): Reason for blocking

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "pattern": "*.spam-site.com",
    "description": "Known spam domain"
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### DELETE /api/v1/blocked-domains

Remove a domain pattern from the blocklist (requires authorization keyword).

**Request:**
```http
DELETE /api/v1/blocked-domains?pattern=*.spam-site.com&keyword=secret-keyword HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Parameters:**
- `pattern` (string, required): Domain pattern to unblock
- `keyword` (string, required): Authorization keyword (from BLOCKED_DOMAIN_KEYWORD env var)

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "pattern": "*.spam-site.com",
    "removed": true
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

## Error Responses

All endpoints return consistent error responses:

### 400 Bad Request

Invalid input or validation error:

```json
{
  "success": false,
  "error": "URL contains dangerous SQL pattern: SELECT",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### 401 Unauthorized

Missing or invalid API key:

```json
{
  "success": false,
  "error": "Unauthorized",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### 404 Not Found

Resource not found:

```json
{
  "success": false,
  "error": "Pattern 'example.com' not found in blocklist",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### 500 Internal Server Error

Server-side error:

```json
{
  "success": false,
  "error": "Internal server error",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

## Rate Limiting

The API implements rate limiting to prevent abuse:

- Default limit: 60 requests per minute per API key
- Configurable via `RATE_LIMIT_PER_MINUTE` environment variable
- Rate limit headers included in responses:
  - `X-RateLimit-Limit`: Maximum requests per window
  - `X-RateLimit-Remaining`: Requests remaining in current window
  - `X-RateLimit-Reset`: Time when the rate limit resets

## Pydantic Models

All request bodies are validated using Pydantic models:

### CrawlRequest
```python
{
  "url": str  # Required, validated URL
}
```

### CrawlStoreRequest
```python
{
  "url": str,           # Required
  "tags": str,          # Optional, max 255 chars
  "retention_policy": str  # Optional: permanent|session_only|30_days
}
```

### DeepCrawlStoreRequest
```python
{
  "url": str,              # Required
  "max_depth": int,        # Optional, 1-5, default 2
  "max_pages": int,        # Optional, 1-250, default 10
  "include_external": bool, # Optional, default false
  "score_threshold": float, # Optional, 0.0-1.0, default 0.0
  "timeout": int,          # Optional, 60-1800 seconds
  "tags": str,            # Optional
  "retention_policy": str  # Optional
}
```

### SearchRequest
```python
{
  "query": str,    # Required, max 500 chars
  "limit": int,    # Optional, 1-1000, default 5
  "tags": str      # Optional, comma-separated
}
```

### TargetSearchRequest
```python
{
  "query": str,           # Required, max 500 chars
  "initial_limit": int,   # Optional, 1-100, default 5
  "expanded_limit": int   # Optional, 1-1000, default 20
}
```

## Testing Endpoints

### Using curl

```bash
# Test health check
curl http://localhost:8080/health

# Get API help
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/help

# Crawl and store a URL
curl -X POST http://localhost:8080/api/v1/crawl/store \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "tags": "test"}'

# Search knowledge base
curl -X POST http://localhost:8080/api/v1/search \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "example", "limit": 5}'

# Get database stats
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/stats

# List blocked domains
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/blocked-domains
```

### Using Python

```python
import requests

API_URL = "http://localhost:8080"
API_KEY = "your-api-key"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Crawl and store
response = requests.post(
    f"{API_URL}/api/v1/crawl/store",
    headers=headers,
    json={"url": "https://example.com", "tags": "python,test"}
)
print(response.json())

# Search
response = requests.post(
    f"{API_URL}/api/v1/search",
    headers=headers,
    json={"query": "python programming", "limit": 10}
)
print(response.json())

# Get stats
response = requests.get(
    f"{API_URL}/api/v1/stats",
    headers=headers
)
print(response.json())
```

## See Also

- [API Overview](index.md)
- [Security Documentation](../advanced/security.md)
- [Batch Operations](../advanced/batch-operations.md)
- [RAM Database Mode](../advanced/ram-database.md)
- [Troubleshooting Guide](../guides/troubleshooting.md)

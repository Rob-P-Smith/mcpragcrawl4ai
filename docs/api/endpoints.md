# API Endpoints

This document provides detailed information about all available REST API endpoints.

## Crawling Endpoints

### POST /api/v1/crawl
Crawl a URL without storing the content.

**Request**
```http
POST /api/v1/crawl HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json
```

**Request Body**
```json
{
  "url": "https://example.com"
}
```

**Parameters**
- `url` (string, required): URL to crawl

**Response**
```json
{
  "success": true,
  "title": "Example Domain",
  "content": "<html><head><title>Example Domain</title></head><body>...",
  "metadata": {
    "status_code": 200,
    "content_type": "text/html"
  }
}
```

### POST /api/v1/crawl/store
Crawl and store content permanently.

**Request**
```http
POST /api/v1/crawl/store HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json
```

**Request Body**
```json
{
  "url": "https://example.com",
  "tags": "example,documentation",
  "retention_policy": "permanent"
}
```

**Parameters**
- `url` (string, required): URL to crawl
- `tags` (string, optional): Comma-separated tags for organization
- `retention_policy` (string, optional): Storage policy ('permanent', 'session_only', '30_days'). Default: 'permanent'

**Response**
```json
{
  "success": true,
  "message": "Content stored successfully",
  "content_id": 12345,
  "preview": "<html><head><title>Example Domain</title></head><body>..."
}
```

### POST /api/v1/crawl/temp
Crawl and store content temporarily (session only).

**Request**
```http
POST /api/v1/crawl/temp HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json
```

**Request Body**
```json
{
  "url": "https://example.com",
  "tags": "temporary,testing"
}
```

**Parameters**
- `url` (string, required): URL to crawl
- `tags` (string, optional): Comma-separated tags for organization

**Response**
```json
{
  "success": true,
  "message": "Content stored temporarily",
  "content_id": 12346,
  "preview": "<html><head><title>Example Domain</title></head><body>..."
}
```

### POST /api/v1/crawl/deep
Deep crawl multiple pages without storing.

**Request**
```http
POST /api/v1/crawl/deep HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json
```

**Request Body**
```json
{
  "url": "https://docs.example.com",
  "max_depth": 3,
  "max_pages": 50,
  "include_external": false
}
```

**Parameters**
- `url` (string, required): Starting URL for deep crawl
- `max_depth` (integer, optional): Maximum depth to crawl (1-5, default: 2)
- `max_pages` (integer, optional): Maximum pages to crawl (1-250, default: 10)
- `include_external` (boolean, optional): Follow external domain links (default: false)
- `score_threshold` (number, optional): Minimum relevance score (0.0-1.0, default: 0.0)
- `timeout` (integer, optional): Maximum crawl time in seconds (default: 300)

**Response**
```json
{
  "success": true,
  "pages_crawled": 25,
  "results": [
    {
      "url": "https://docs.example.com/page1",
      "title": "Page 1 Title",
      "preview": "<html><head><title>Page 1</title></head><body>..."
    },
    {
      "url": "https://docs.example.com/page2",
      "title": "Page 2 Title",
      "preview": "<html><head><title>Page 2</title></head><body>..."
    }
  ]
}
```

### POST /api/v1/crawl/deep/store
Deep crawl and store all discovered pages.

**Request**
```http
POST /api/v1/crawl/deep/store HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json
```

**Request Body**
```json
{
  "url": "https://docs.example.com",
  "retention_policy": "permanent",
  "tags": "deep_crawl,documentation",
  "max_depth": 3,
  "max_pages": 50,
  "include_external": false
}
```

**Parameters**
- `url` (string, required): Starting URL for deep crawl
- `retention_policy` (string, optional): Storage policy ('permanent', 'session_only', etc.). Default: 'permanent'
- `tags` (string, optional): Tags for content organization (auto-adds 'deep_crawl')
- `max_depth` (integer, optional): Maximum depth to crawl (1-5, default: 2)
- `max_pages` (integer, optional): Maximum pages to crawl (1-250, default: 10)
- `include_external` (boolean, optional): Follow external domain links (default: false)
- `score_threshold` (number, optional): Minimum relevance score (0.0-1.0, default: 0.0)
- `timeout` (integer, optional): Maximum crawl time in seconds (default: 300)

**Response**
```json
{
  "success": true,
  "storage_summary": {
    "total_pages_crawled": 50,
    "successful_stores": 48,
    "failed_stores": 2,
    "error_details": [
      {
        "url": "https://docs.example.com/broken-link",
        "error": "Connection timeout"
      }
    ]
  },
  "stored_pages": [
    {
      "url": "https://docs.example.com/page1",
      "content_id": 12347,
      "tags": "deep_crawl,documentation"
    },
    {
      "url": "https://docs.example.com/page2",
      "content_id": 12348,
      "tags": "deep_crawl,documentation"
    }
  ]
}
```

## Knowledge Base Endpoints

### POST /api/v1/search
Search stored knowledge using semantic similarity.

**Request**
```http
POST /api/v1/search HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json
```

**Request Body**
```json
{
  "query": "machine learning algorithms",
  "limit": 10
}
```

**Parameters**
- `query` (string, required): Search query text
- `limit` (integer, optional): Number of results (default: 5)

**Response**
```json
{
  "results": [
    {
      "url": "https://docs.example.com/ml-algorithms",
      "title": "Machine Learning Algorithms Guide",
      "content": "This guide covers various machine learning algorithms...",
      "timestamp": "2023-10-15T14:30:00Z",
      "tags": "ml,algorithms,guide",
      "similarity_score": 0.92
    },
    {
      "url": "https://docs.example.com/ai-models",
      "title": "AI Model Comparison",
      "content": "Comparison of different AI models and their performance...",
      "timestamp": "2023-10-14T09:15:00Z",
      "tags": "ai,models,comparison",
      "similarity_score": 0.87
    }
  ]
}
```

### GET /api/v1/memory
List all stored content.

**Request**
```http
GET /api/v1/memory?filter=permanent HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Parameters**
- `filter` (string, optional): Filter by retention policy ('permanent', 'session_only', '30_days')

**Response**
```json
{
  "content": [
    {
      "url": "https://docs.example.com/ml-algorithms",
      "title": "Machine Learning Algorithms Guide",
      "timestamp": "2023-10-15T14:30:00Z",
      "tags": "ml,algorithms,guide",
      "retention_policy": "permanent"
    },
    {
      "url": "https://docs.example.com/ai-models",
      "title": "AI Model Comparison",
      "timestamp": "2023-10-14T09:15:00Z",
      "tags": "ai,models,comparison",
      "retention_policy": "permanent"
    }
  ]
}
```

### DELETE /api/v1/memory
Remove specific content by URL.

**Request**
```http
DELETE /api/v1/memory HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
Content-Type: application/json
```

**Request Body**
```json
{
  "url": "https://example.com"
}
```

**Parameters**
- `url` (string, required): URL to remove

**Response**
```json
{
  "success": true,
  "message": "Content removed successfully",
  "removed_count": 1
}
```

### DELETE /api/v1/memory/temp
Clear all temporary content.

**Request**
```http
DELETE /api/v1/memory/temp HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Response**
```json
{
  "success": true,
  "message": "All temporary content cleared",
  "cleared_count": 5
}
```

## System Endpoints

### GET /api/v1/status
Get system status and health information.

**Request**
```http
GET /api/v1/status HTTP/1.1
Host: localhost:8080
Authorization: Bearer your-api-key
```

**Response**
```json
{
  "status": "healthy",
  "uptime": "24h35m12s",
  "memory_usage": {
    "total": "1.2GB",
    "used": "678MB",
    "free": "522MB"
  },
  "database_status": {
    "connection": "active",
    "size": "450MB",
    "tables": [
      "crawled_content",
      "sessions",
      "content_vectors"
    ]
  },
  "api_stats": {
    "requests_total": 1234,
    "errors_last_hour": 2
  }
}
```

### GET /health
Basic health check endpoint.

**Request**
```http
GET /health HTTP/1.1
Host: localhost:8080
```

**Response**
```json
{
  "status": "ok",
  "timestamp": "2023-10-15T14:30:00Z"
}

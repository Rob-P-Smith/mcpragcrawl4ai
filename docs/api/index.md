# API Reference

This documentation covers the REST API layer that enables bidirectional communication between local MCP servers and remote deployments.

## Overview

The Crawl4AI RAG MCP Server provides a comprehensive REST API with 18 endpoints for web crawling, knowledge management, and system administration. The system can operate in two modes:

- **Server Mode**: Hosts REST API endpoints for remote clients
- **Client Mode**: Forwards MCP tool calls to a remote REST API server

All endpoints require authentication using an API key via the Authorization header with Bearer token format.

## Key Features

### High-Performance RAM Database
- **10-50x faster** than traditional disk-based operations
- Intelligent differential synchronization to disk
- Automatic idle and periodic sync
- Check RAM database status with the `using_ram_db` flag in `/api/v1/stats`
- Monitor sync health via `/api/v1/db/stats`
- See [RAM Database Mode](../advanced/ram-database.md) for details

### Advanced Security
- **SQL injection protection** with pattern detection and keyword filtering
- **Domain blocking** system with wildcard pattern support (e.g., `*.ru`, `*spam*`)
- **Input sanitization** for all user-provided data
- **Adult content filtering** to prevent inappropriate URL crawling
- See [Security Documentation](../advanced/security.md) for details

### Batch Operations
- Deep crawling with DFS strategy (up to 250 pages)
- Intelligent search with tag discovery
- Bulk memory management
- See [Batch Operations](../advanced/batch-operations.md) for details

## API Endpoints Summary

For detailed endpoint documentation with request/response examples, see [API Endpoints](endpoints.md).

### System Endpoints (3)

- `GET /health` - Basic health check endpoint (no auth required)
- `GET /api/v1/status` - Get comprehensive system status and health
- `GET /api/v1/help` - Get help documentation for all available tools

### Crawling Endpoints (4)

- `POST /api/v1/crawl` - Crawl a URL without storing content
- `POST /api/v1/crawl/store` - Crawl and store content permanently
- `POST /api/v1/crawl/temp` - Crawl and store content temporarily (session only)
- `POST /api/v1/crawl/deep/store` - Deep crawl and store all discovered pages (DFS)

### Search Endpoints (2)

- `POST /api/v1/search` - Search stored knowledge using semantic similarity
- `POST /api/v1/search/target` - Intelligent search with automatic tag discovery and expansion

### Knowledge Base Management (3)

- `GET /api/v1/memory` - List all stored content with filtering options
- `DELETE /api/v1/memory` - Remove specific content by URL
- `DELETE /api/v1/memory/temp` - Clear all temporary session content

### Database Statistics (3)

- `GET /api/v1/stats` - Get comprehensive database statistics and storage breakdown
- `GET /api/v1/db/stats` - Get RAM database sync metrics and health status
- `GET /api/v1/domains` - List all unique domains with page counts

### Domain Blocking (3)

- `GET /api/v1/blocked-domains` - List all blocked domain patterns
- `POST /api/v1/blocked-domains` - Add a domain pattern to the blocklist
- `DELETE /api/v1/blocked-domains` - Remove a domain pattern (requires authorization keyword)

## Authentication

All endpoints require authentication using an API key via the Authorization header:

```http
Authorization: Bearer your-api-key
```

The API key is configured through environment variables:
- `LOCAL_API_KEY`: For server mode authentication
- `REMOTE_API_KEY`: For client mode remote requests

## Rate Limiting

The system implements rate limiting to prevent abuse:
- **Default limit**: 60 requests per minute per API key
- **Configurable**: Set `RATE_LIMIT_PER_MINUTE` environment variable
- **Response headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Error Handling

All error responses follow a consistent format:

```json
{
  "success": false,
  "error": "Error message description",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### Common Error Scenarios

- **400 Bad Request**: Invalid input or validation error (e.g., SQL injection pattern detected, URL blocked)
- **401 Unauthorized**: Missing or invalid API key
- **404 Not Found**: Resource not found (e.g., URL not in memory, blocked domain pattern not found)
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server-side error

## Security Features

### Input Validation
All user inputs are sanitized before processing to prevent:
- SQL injection attacks via keyword detection and pattern matching
- XSS attacks through HTML/JavaScript filtering
- Buffer overflow via strict length limits
- Invalid data types through type validation

### Domain Blocking
The system maintains a database of blocked domain patterns:
- **Wildcard TLD blocking**: `*.ru` blocks all .ru domains
- **Keyword blocking**: `*spam*` blocks any URL containing "spam"
- **Exact domain blocking**: `example.com` blocks that specific domain

Default blocks include common adult content patterns and high-risk TLDs. Manage blocked domains via the `/api/v1/blocked-domains` endpoints.

### Authorization
Sensitive operations require additional authorization:
- **Domain unblocking**: Requires `BLOCKED_DOMAIN_KEYWORD` environment variable
- **API access**: All endpoints require valid Bearer token (except `/health`)

## Performance Considerations

### RAM Database Mode
When `USE_MEMORY_DB=true`:
- All database operations run in memory for maximum speed
- Automatic differential sync to disk every 5 seconds after writes
- Periodic sync every 5 minutes as backup
- Check sync status via `/api/v1/db/stats`

Performance benefits:
- **Read operations**: 10-100x faster than disk
- **Write operations**: 5-10x faster than disk
- **Vector searches**: Near-instant results

### Monitoring
Monitor system health and performance:
- `/api/v1/status` - Component health status
- `/api/v1/stats` - Database statistics, storage breakdown, retention policies
- `/api/v1/db/stats` - RAM database sync metrics and health

## Advanced Features

For detailed documentation on advanced features:

- **[RAM Database Mode](../advanced/ram-database.md)** - High-performance in-memory database with automatic persistence
- **[Security Layer](../advanced/security.md)** - Comprehensive input sanitization and domain blocking
- **[Batch Operations](../advanced/batch-operations.md)** - Deep crawling, bulk operations, and advanced workflows

## Getting Started

1. **Quick Start**: See [Quick Start Guide](../guides/quick-start.md) for setup instructions
2. **Deployment**: See [Deployment Guide](../guides/deployment.md) for production deployment
3. **API Reference**: See [API Endpoints](endpoints.md) for detailed endpoint documentation
4. **Troubleshooting**: See [Troubleshooting Guide](../guides/troubleshooting.md) for common issues
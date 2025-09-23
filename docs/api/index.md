# API Reference

This documentation covers the REST API layer that enables bidirectional communication between local MCP servers and remote deployments.

## Overview

The system can operate in two modes:
- **Server Mode**: Hosts REST API endpoints for remote clients
- **Client Mode**: Forwards MCP tool calls to a remote REST API server

All endpoints require authentication using an API key via the Authorization header with Bearer token format.

## Endpoints

For detailed endpoint documentation, see [API Endpoints](endpoints.md).

### Crawling Endpoints

- `POST /api/v1/crawl` - Crawl a URL without storing content
- `POST /api/v1/crawl/store` - Crawl and store content permanently
- `POST /api/v1/crawl/temp` - Crawl and store content temporarily (session only)
- `POST /api/v1/crawl/deep` - Deep crawl multiple pages without storing
- `POST /api/v1/crawl/deep/store` - Deep crawl and store all discovered pages

### Knowledge Base Endpoints

- `POST /api/v1/search` - Search stored knowledge using semantic similarity
- `GET /api/v1/memory` - List all stored content
- `DELETE /api/v1/memory` - Remove specific content by URL
- `DELETE /api/v1/memory/temp` - Clear all temporary content

### System Endpoints

- `GET /api/v1/status` - Get system status and health information
- `GET /health` - Basic health check endpoint

## Authentication

All endpoints require authentication using an API key via the Authorization header:

```http
Authorization: Bearer your-api-key
```

The API key is configured through environment variables:
- `LOCAL_API_KEY`: For server mode authentication
- `REMOTE_API_KEY`: For client mode remote requests

## Rate Limiting

The system implements rate limiting to prevent abuse. The default limit is 60 requests per minute per API key, which can be configured via the `RATE_LIMIT_PER_MINUTE` environment variable.

## Error Handling

All error responses follow a consistent format:

```json
{
  "error": "Error message",
  "code": "error_code"
}
```

Common error codes include:
- `401`: Unauthorized (invalid or missing API key)
- `403`: Forbidden (insufficient permissions)
- `429`: Too many requests (rate limit exceeded)
- `500`: Internal server error

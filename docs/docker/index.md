# Docker Setup Guide

A complete Docker-based setup for a Retrieval-Augmented Generation (RAG) system using Crawl4AI, sqlite-vec, and MCP integration with OpenWebUI support.

## Overview

This guide provides instructions for setting up the RAG system using Docker containers. The architecture includes:
- **Crawl4AI Container**: Handles web content extraction
- **MCP Server + MCPO Container**: Runs the Python-based RAG server with REST API endpoints and OpenWebUI integration

The setup supports both local development and remote deployment scenarios.

## Quick Start

### Prerequisites
- Docker and docker-compose installed
- At least 4GB RAM available
- 10GB free disk space

### Build and Deploy

1. **Build the Docker image**:
```bash
docker build -t crawl4ai-mcp-server:latest .
```

2. **Start the services**:
```bash
docker compose up -d
```

3. **Verify services are running**:
```bash
docker compose ps
```

You should see both `crawl4ai` and `crawl4ai-mcp-server` containers running.

## Remote Access via OpenWebUI

The MCP server is accessible remotely via MCPO (MCP-to-OpenAPI proxy) for OpenWebUI integration:

### OpenWebUI Connection Setup

1. **Access URL**: `http://your-server-ip:8765/openapi.json`
2. **In OpenWebUI**: Add Connection → OpenAPI
3. **Configuration**:
   - URL: `http://your-server-ip:8765`
   - Auth: Session (no API key required)
   - Name: Any descriptive name

### Available API Endpoints

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

## Batch Crawling with Docker

### Running Batch Crawler

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

### Monitoring Batch Progress

```bash
# Watch batch crawler logs
docker logs -f crawl4ai-mcp-server

# Check database statistics
docker exec -it crawl4ai-mcp-server python3 dbstats.py
```

## Architecture

```
┌─────────────────┐    ┌──────────────────────┐
│   Crawl4AI      │    │  MCP Server + MCPO   │
│   Container     │◄───┤  Container           │
│   Port: 11235   │    │  Port: 8765          │
└─────────────────┘    └──────────────────────┘
                                │
                       ┌────────▼────────┐
                       │   Data Volume   │
                       │  ./data:/app/   │
                       │     data/       │
                       └─────────────────┘
```

### Service Details

**crawl4ai container**:
- Runs official Crawl4AI Docker image
- Handles web content extraction
- Internal network communication only

**mcp-server container**:
- Custom-built container with Python dependencies
- Runs both MCP server and MCPO proxy
- Exposes port 8765 for OpenWebUI access
- Mounts `./data` for database persistence

### Database Management

**Database Location**: `./data/crawl4ai_rag.db` (persisted on host)
**Migration**: Copy existing database to `./data/` directory
**Backup**: Regular SQLite backup of the data directory

## Manual Database Operations

### Database Statistics
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

### Backup and Restore
```bash
# Backup database
cp ./data/crawl4ai_rag.db ./data/crawl4ai_rag.db.backup

# Restore from backup
cp ./data/crawl4ai_rag.db.backup ./data/crawl4ai_rag.db

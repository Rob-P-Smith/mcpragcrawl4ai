# Crawl4AI RAG MCP Server - Documentation

Complete documentation for the Crawl4AI RAG (Retrieval-Augmented Generation) MCP Server implementation.

## Overview

This system provides a local homelab-friendly RAG solution that combines:
- **Crawl4AI** for web content extraction
- **SQLite + sqlite-vec** for vector storage and semantic search
- **LM-Studio MCP integration** for AI assistant interaction
- **REST API layer** for bidirectional communication

## Quick Links

### Getting Started
- [Quick Start Guide](guides/quick-start.md) - Get up and running quickly
- [Deployment Guide](deployments.md) - Comprehensive deployment options
- [Installation Guide](#installation-guide) - Detailed setup instructions

### API & Integration
- [API Documentation](API_README.md) - REST API reference
- [API Endpoints](api/endpoints.md) - Detailed endpoint documentation
- [Docker Setup](docker/index.md) - Docker deployment guide

### Guides
- [Deployment Options](deployments.md) - Server, Client, and Local deployment
- [Troubleshooting](guides/troubleshooting.md) - Common issues and solutions
- [Full Documentation](index.md) - Complete documentation index

## Architecture

```
┌─────────────┐
│  LM-Studio   │
│  (MCP Client)│
└──────┬──────┘
       │
┌──────▼────────────┐
│   MCP Server      │
│ (core/rag_        │
│  processor.py)    │
└──────┬────────────┘
       │
┌──────▼────────────┐      ┌──────────────┐
│  RAG System       │──────│  Crawl4AI    │
│  (operations/     │      │ (Docker:     │
│   crawler.py)     │      │  port 11235) │
└──────┬────────────┘      └──────────────┘
       │
┌──────▼────────────┐
│  Vector Database  │
│  (SQLite +        │
│   sqlite-vec)     │
└───────────────────┘
```

## Installation Guide

### Prerequisites

- Ubuntu/Linux system or macOS
- Docker installed
- Python 3.8 or higher
- At least 4GB RAM available
- 10GB free disk space

### Quick Setup

1. **Clone repository**:
```bash
git clone https://github.com/Rob-P-Smith/mcpragcrawl4ai.git
cd mcpragcrawl4ai
```

2. **Install dependencies**:
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

3. **Start Crawl4AI**:
```bash
docker run -d --name crawl4ai -p 11235:11235 unclecode/crawl4ai:latest
```

4. **Configure environment**:
```bash
cat > .env << EOF
IS_SERVER=true
LOCAL_API_KEY=$(openssl rand -base64 32)
CRAWL4AI_URL=http://localhost:11235
EOF
```

5. **Run MCP server**:
```bash
python3 core/rag_processor.py
```

For detailed instructions, see the [Quick Start Guide](guides/quick-start.md).

## Project Structure

### Core Components

- **core/rag_processor.py**: Main MCP server implementation and JSON-RPC handling
- **core/operations/crawler.py**: Web crawling logic and deep crawling functionality
- **core/data/storage.py**: Database operations, content storage, and vector embeddings
- **core/utilities/**: Helper scripts for testing and batch operations

### API Layer

- **api/api.py**: FastAPI server with all REST endpoints
- **api/auth.py**: Authentication middleware and session management

### Deployment Configurations

- **deployments/server/**: Server deployment (REST API + MCP server in Docker)
- **deployments/client/**: Client deployment (lightweight MCP client forwarder)

## Available Tools

The MCP server provides the following tools:

### Basic Crawling
1. **crawl_url** - Crawl without storing
2. **crawl_and_remember** - Crawl and store permanently
3. **crawl_temp** - Crawl and store temporarily (session-only)

### Deep Crawling
4. **deep_crawl_dfs** - Deep crawl multiple pages using depth-first search without storing
5. **deep_crawl_and_store** - Deep crawl multiple pages using DFS and store all in knowledge base

### Knowledge Management
6. **search_memory** - Semantic search of stored content
7. **list_memory** - List all stored content with optional filtering
8. **forget_url** - Remove specific content by URL
9. **clear_temp_memory** - Clear temporary session content

## Deployment Options

### Local Development
Run directly on your machine with Python virtual environment.
- [Local Development Guide](guides/deployment.md#local-development-environment)

### Docker Server Deployment
Full-featured server with REST API + MCP server in Docker.
- [Server Deployment Guide](deployments.md#deployment-option-1-server-deployment)
- [Server README](../deployments/server/README.md)

### Docker Client Deployment
Lightweight client forwarding requests to remote server.
- [Client Deployment Guide](deployments.md#deployment-option-2-client-deployment)
- [Client README](../deployments/client/README.md)

## Configuration

### Environment Variables

**Core Settings:**
- `IS_SERVER` - `true` for server mode, `false` for client mode
- `SERVER_HOST` - Host to bind API server (default: `0.0.0.0`)
- `SERVER_PORT` - Port for API server (default: `8080`)

**Authentication:**
- `LOCAL_API_KEY` - API key for server mode
- `REMOTE_API_KEY` - API key for client mode
- `REMOTE_API_URL` - Remote server URL for client mode

**Database:**
- `DB_PATH` - SQLite database path (default: `crawl4ai_rag.db`)

**Services:**
- `CRAWL4AI_URL` - Crawl4AI service URL (default: `http://localhost:11235`)

### LM-Studio Configuration

For local development:
```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "/path/to/.venv/bin/python3",
      "args": ["/path/to/core/rag_processor.py"]
    }
  }
}
```

For Docker server deployment:
```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "socat",
      "args": ["-", "TCP:localhost:3000"]
    }
  }
}
```

For Docker client deployment:
```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "docker",
      "args": ["exec", "-i", "crawl4ai-mcp-client", "python3", "core/rag_processor.py"]
    }
  }
}
```

## Features

- **Local Homelab Deployment**: Runs entirely on your personal computer or home server
- **MCP Integration**: Works seamlessly with LM-Studio and other MCP-compatible AI assistants
- **Semantic Search**: Vector-based content retrieval using sqlite-vec
- **Bidirectional Communication**: REST API layer supports both server and client modes
- **Deep Crawling**: Advanced DFS crawling with customizable parameters (max depth 5, max pages 250)
- **Content Management**: Full CRUD operations for stored content
- **Security**: API key authentication and rate limiting
- **Session Management**: Automatic cleanup of temporary content

## Deep Crawling Features

- **DFS Strategy**: Uses depth-first search to crawl multiple interconnected pages
- **Configurable Depth**: Control how many levels deep to crawl (max 5 levels)
- **Page Limits**: Restrict maximum pages crawled to prevent resource exhaustion (max 250 pages)
- **External Links**: Option to follow or ignore external domain links
- **URL Scoring**: Filter pages based on relevance scores (0.0-1.0 threshold)
- **Bulk Storage**: Store all discovered pages in the knowledge base with automatic tagging

## Data Persistence

- **Database**: SQLite file in the configured location (default: `crawl4ai_rag.db`)
- **Content Chunking**: Text split into 500-word chunks with 50-word overlap
- **Retention Policies**: 'permanent', 'session_only', or time-based (e.g., '30_days')
- **Deep Crawl Tags**: Automatically tagged with 'deep_crawl' and depth information
- **Vector Embeddings**: 384-dimensional vectors using sentence-transformers 'all-MiniLM-L6-v2'

## Development Commands

### Running the MCP Server
```bash
# Run the main MCP server (local mode)
python3 core/rag_processor.py

# Run in client mode (forwards to remote API)
# First set IS_SERVER=false in .env
python3 core/rag_processor.py
```

### Running the REST API Server
```bash
# Start API server (server mode)
python3 deployments/server/start_api_server.py

# Or use uvicorn directly
uvicorn api.api:create_app --host 0.0.0.0 --port 8080
```

### Testing
```bash
# Test sqlite-vec installation
python3 core/utilities/test_sqlite_vec.py

# Test database operations
python3 core/utilities/dbstats.py

# Test batch crawling functionality
python3 core/utilities/batch_crawler.py
```

### Docker Operations
```bash
# Server Deployment (REST API + MCP Server)
docker compose -f deployments/server/docker-compose.yml up -d
docker compose -f deployments/server/docker-compose.yml logs -f
docker compose -f deployments/server/docker-compose.yml down

# Client Deployment (MCP Client only)
docker compose -f deployments/client/docker-compose.yml up -d
docker compose -f deployments/client/docker-compose.yml logs -f
docker compose -f deployments/client/docker-compose.yml down

# Standalone Crawl4AI service
docker run -d --name crawl4ai -p 11235:11235 unclecode/crawl4ai:latest
```

## Troubleshooting

For common issues and solutions, see the [Troubleshooting Guide](guides/troubleshooting.md).

### Quick Diagnostics

**Check Services:**
```bash
# Check Docker containers
docker ps

# Check ports
sudo lsof -i :8080  # REST API
sudo lsof -i :3000  # MCP Server
sudo lsof -i :11235 # Crawl4AI
```

**Test Connectivity:**
```bash
# Test REST API
curl http://localhost:8080/health

# Test Crawl4AI
curl http://localhost:11235/
```

**View Logs:**
```bash
# Application errors
tail -f data/crawl4ai_rag_errors.log

# Docker logs
docker logs crawl4ai
docker logs crawl4ai-rag-server
```

## Support

- [GitHub Issues](https://github.com/Rob-P-Smith/mcpragcrawl4ai/issues)
- [AGENTS.md](../AGENTS.md) - Developer guide
- [Troubleshooting Guide](guides/troubleshooting.md)
- [Deployment Guide](deployments.md)

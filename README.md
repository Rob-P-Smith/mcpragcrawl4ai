# Crawl4AI RAG MCP Server

A complete Retrieval-Augmented Generation (RAG) system using Crawl4AI for web content extraction, sqlite-vec for vector storage, and LM-Studio MCP integration.

## Summary

This system provides a local homelab-friendly RAG solution that combines:
- Crawl4AI for web content extraction
- SQLite with sqlite-vec for vector storage and semantic search
- LM-Studio MCP integration for AI assistant interaction
- REST API layer for bidirectional communication

## Quick Start

### Option 1: Local Development

1. **Clone and setup**:
```bash
git clone https://github.com/Rob-P-Smith/mcpragcrawl4ai.git
cd mcpragcrawl4ai
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

2. **Start Crawl4AI service**:
```bash
docker run -d --name crawl4ai -p 11235:11235 unclecode/crawl4ai:latest
```

3. **Configure environment**:
```bash
# Create .env file
cat > .env << EOF
IS_SERVER=true
LOCAL_API_KEY=dev-api-key
CRAWL4AI_URL=http://localhost:11235
EOF
```

4. **Run MCP server**:
```bash
python3 core/rag_processor.py
```

### Option 2: Docker Server Deployment

1. **Deploy full server** (REST API + MCP):
```bash
cd mcpragcrawl4ai
docker compose -f deployments/server/docker-compose.yml up -d
```

2. **Test deployment**:
```bash
curl http://localhost:8080/health
```

See [Deployment Guide](docs/deployments.md) for complete deployment options.

## Documentation

For detailed documentation, see:
- [Deployment Guide](docs/deployments.md) - Comprehensive deployment options
- [Installation Guide](docs/README.md) - Setup and configuration
- [API Documentation](docs/API_README.md) - REST API reference
- [Quick Start Guide](docs/guides/quick-start.md) - Get started quickly
- [Troubleshooting](docs/guides/troubleshooting.md) - Common issues and solutions
- [Full Documentation](docs/index.md) - Complete documentation index

## Features

- **Local Homelab Deployment**: Runs entirely on your personal computer or home server
- **MCP Integration**: Works seamlessly with LM-Studio and other MCP-compatible AI assistants
- **Semantic Search**: Vector-based content retrieval using sqlite-vec
- **Bidirectional Communication**: REST API layer supports both server and client modes
- **Deep Crawling**: Advanced DFS crawling with customizable parameters
- **Content Management**: Full CRUD operations for stored content
- **Security**: API key authentication and rate limiting

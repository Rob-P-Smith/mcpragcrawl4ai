# Crawl4AI RAG MCP Server

A complete Retrieval-Augmented Generation (RAG) system using Crawl4AI for web content extraction, sqlite-vec for vector storage, and LM-Studio MCP integration.

## Summary

This system provides a local homelab-friendly RAG solution that combines:
- Crawl4AI for web content extraction
- SQLite with sqlite-vec for vector storage and semantic search
- LM-Studio MCP integration for AI assistant interaction
- REST API layer for bidirectional communication

## Quick Start

1. **Clone and setup**:
```bash
git clone https://github.com/Rob-P-Smith/mcpragcrawl4ai.git
cd mcpragcrawl4ai
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Start Docker containers**:
```bash
docker-compose up -d
```

4. **Configure LM-Studio**:
   - Open LM-Studio and go to Program → View MCP Configuration
   - Update the mcp.json file with the correct paths to your virtual environment and script

5. **Test the setup**:
```bash
# Test basic functionality
python3 core/rag_processor.py &
sleep 5
kill %1
```

## Documentation

For detailed documentation, see:
- [Installation Guide](docs/README.md)
- [API Documentation](docs/API_README.md) 
- [Docker Setup](docs/mcpragDocker.md)
- [Full Documentation](docs/index.md)

## Features

- **Local Homelab Deployment**: Runs entirely on your personal computer or home server
- **MCP Integration**: Works seamlessly with LM-Studio and other MCP-compatible AI assistants
- **Semantic Search**: Vector-based content retrieval using sqlite-vec
- **Bidirectional Communication**: REST API layer supports both server and client modes
- **Deep Crawling**: Advanced DFS crawling with customizable parameters
- **Content Management**: Full CRUD operations for stored content
- **Security**: API key authentication and rate limiting

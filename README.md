# Crawl4AI RAG MCP Server

A high-performance Retrieval-Augmented Generation (RAG) system using Crawl4AI for web content extraction, sqlite-vec for vector storage, and MCP integration for AI assistants.

## Summary

This system provides a production-ready RAG solution that combines:
- **Crawl4AI** for intelligent web content extraction with markdown conversion
- **SQLite with sqlite-vec** for vector storage and semantic search
- **RAM Database Mode** for 10-50x faster query performance
- **MCP Server** for AI assistant integration (LM-Studio, Claude Desktop, etc.)
- **REST API** for bidirectional communication and remote access
- **Security Layer** with input sanitization and domain blocking

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
USE_MEMORY_DB=true
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

## Architecture

### Core Components
- **MCP Server** (core/rag_processor.py) - JSON-RPC 2.0 protocol handler
- **RAG Database** (core/data/storage.py) - SQLite + sqlite-vec vector storage
- **Sync Manager** (core/data/sync_manager.py) - RAM database differential sync
- **Crawler** (core/operations/crawler.py) - Web crawling with DFS algorithm
- **Defense Layer** (core/data/dbdefense.py) - Input sanitization and security
- **REST API** (api/api.py) - FastAPI server with 15+ endpoints
- **Auth System** (api/auth.py) - API key authentication and rate limiting

### Database Schema
- **crawled_content** - Web content with markdown, embeddings, and metadata
- **content_vectors** - Vector embeddings (sqlite-vec virtual table)
- **sessions** - User session tracking for temporary content
- **blocked_domains** - Domain blocklist with wildcard patterns
- **_sync_tracker** - Change tracking for RAM database sync (memory mode only)

### Technology Stack
- **Python 3.11+** with asyncio for concurrent operations
- **SQLite** with sqlite-vec extension for vector similarity search
- **SentenceTransformers** (all-MiniLM-L6-v2) for embedding generation
- **FastAPI** for REST API with automatic OpenAPI documentation
- **Crawl4AI** for intelligent web content extraction
- **Docker** for containerized deployment

## Documentation

For detailed documentation, see:
- [Deployment Guide](docs/deployments.md) - Comprehensive deployment options
- [Installation Guide](docs/README.md) - Setup and configuration
- [API Documentation](docs/API_README.md) - REST API reference
- [Quick Start Guide](docs/guides/quick-start.md) - Get started quickly
- [Troubleshooting](docs/guides/troubleshooting.md) - Common issues and solutions
- [Full Documentation](docs/index.md) - Complete documentation index

## Key Features

### Performance
- **RAM Database Mode**: In-memory SQLite with differential sync for 10-50x faster queries
- **Vector Search**: 384-dimensional embeddings using all-MiniLM-L6-v2 for semantic search
- **Batch Crawling**: High-performance batch processing with retry logic and progress tracking
- **Efficient Storage**: Markdown conversion and content chunking for optimal retrieval

### Functionality
- **Deep Crawling**: DFS-based multi-page crawling with depth and page limits
- **Semantic Search**: Vector similarity search with tag filtering and deduplication
- **Target Search**: Intelligent search with automatic tag expansion
- **Content Management**: Full CRUD operations with retention policies and session management

### Security
- **Input Sanitization**: Comprehensive SQL injection defense and input validation
- **Domain Blocking**: Wildcard-based domain blocking with social media and adult content filters
- **API Authentication**: API key-based authentication with rate limiting
- **Safe Crawling**: Automatic detection and blocking of forbidden content

### Integration
- **MCP Server**: Full MCP protocol support for AI assistant integration
- **REST API**: Complete REST API with 15+ endpoints for all operations
- **Bidirectional Mode**: Server mode (host API) and client mode (forward to remote)
- **Docker Deployment**: Production-ready containerized deployment

## Quick Usage Examples

### Via MCP (in LM-Studio/Claude Desktop)
```
crawl_and_remember("https://docs.python.org/3/tutorial/", tags="python, tutorial")
search_memory("list comprehensions", tags="python", limit=5)
target_search("async programming best practices", initial_limit=5, expanded_limit=20)
get_database_stats()
```

### Via REST API
```bash
# Crawl and store content
curl -X POST http://localhost:8080/api/v1/crawl/store \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.python.org/3/tutorial/", "tags": "python, tutorial"}'

# Semantic search
curl -X POST http://localhost:8080/api/v1/search \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "list comprehensions", "tags": "python", "limit": 5}'

# Get database stats
curl http://localhost:8080/api/v1/stats \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Via Python Client
```python
from api.api import Crawl4AIClient

client = Crawl4AIClient("http://localhost:8080", "YOUR_API_KEY")
result = await client.crawl_and_store("https://example.com", tags="example")
search_results = await client.search("python tutorials", limit=10)
stats = await client.get_database_stats()
```

## Performance Metrics

With RAM database mode enabled:
- **Search queries**: 20-50ms (vs 200-500ms disk mode)
- **Batch crawling**: 2,000+ URLs successfully processed
- **Database size**: 205MB (2,018 pages, 9,743 embeddings)
- **Sync overhead**: <100ms for differential sync
- **Memory usage**: ~500MB for full in-memory database

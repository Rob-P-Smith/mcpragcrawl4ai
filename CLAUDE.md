# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is a Crawl4AI RAG (Retrieval-Augmented Generation) MCP Server implementation that provides web crawling capabilities with semantic search and knowledge base storage. The main implementation is in `crawl4ai_rag_optimized.py`.

## Key Components

### Core Architecture
- **MCPServer**: Main server handling JSON-RPC 2.0 protocol for MCP communication
- **Crawl4AIRAG**: Web crawling interface that communicates with a local Crawl4AI service
- **RAGDatabase**: SQLite-based vector database using sqlite-vec extension for semantic search
- **Error Logging**: Comprehensive error logging system writing to `crawl4ai_rag_errors.log`

### Dependencies
- **External Service**: Requires Crawl4AI service running on `http://localhost:11235`
- **Vector Database**: Uses sqlite-vec extension for vector similarity search
- **ML Model**: Pre-loads SentenceTransformer 'all-MiniLM-L6-v2' for embeddings
- **Key Libraries**: sqlite3, sqlite_vec, sentence_transformers, numpy, requests

### File Structure
- **core/rag_processor.py**: Main MCP server implementation and JSON-RPC handling
- **operations/crawler.py**: Web crawling logic and deep crawling functionality
- **data/storage.py**: Database operations, content storage, and vector embeddings
- **utilities/**: Helper scripts for testing and batch operations
- **api/**: REST API module for bidirectional communication
  - **api/api.py**: FastAPI server with all REST endpoints
  - **api/auth.py**: Authentication middleware and session management

### Database Schema
- **crawled_content**: Stores web content with metadata, retention policies, and session tracking
- **sessions**: Tracks user sessions for temporary content management  
- **content_vectors**: Virtual table for vector embeddings using vec0 engine

## Available Tools
1. **crawl_url**: Crawl without storing
2. **crawl_and_remember**: Crawl and store permanently
3. **crawl_temp**: Crawl and store temporarily (session-only)
4. **search_memory**: Semantic search of stored content
5. **list_memory**: List all stored content with optional filtering
6. **forget_url**: Remove specific content by URL
7. **clear_temp_memory**: Clear temporary session content
8. **deep_crawl_dfs**: Deep crawl multiple pages using depth-first search without storing
9. **deep_crawl_and_store**: Deep crawl multiple pages using DFS and store all in knowledge base

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
python3 start_api_server.py

# Or use uvicorn directly
uvicorn api.api:create_app --host 0.0.0.0 --port 8080

# Install API dependencies first
pip install -r requirements.txt
```

### Testing
```bash
# Test sqlite-vec installation
python3 utilities/test_sqlite_vec.py

# Test database operations
python3 utilities/dbstats.py

# Test batch crawling functionality
python3 utilities/batch_crawler.py
```

### Docker Operations
```bash
# Start Crawl4AI service
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs crawl4ai

# Stop services
docker-compose down
```

The server expects JSON-RPC 2.0 requests via stdin and responds via stdout. Errors are logged to both stderr and the log file.

## Deep Crawling Features
- **DFS Strategy**: Uses depth-first search to crawl multiple interconnected pages
- **Configurable Depth**: Control how many levels deep to crawl (max 5 levels)
- **Page Limits**: Restrict maximum pages crawled to prevent resource exhaustion (max 100 pages)
- **External Links**: Option to follow or ignore external domain links
- **URL Scoring**: Filter pages based on relevance scores (0.0-1.0 threshold)
- **Bulk Storage**: Store all discovered pages in the knowledge base with automatic tagging

## Data Persistence
- **Database**: SQLite file `crawl4ai_rag.db` in the working directory
- **Content Chunking**: Text split into 500-word chunks with 50-word overlap
- **Retention Policies**: 'permanent', 'session_only', or time-based (e.g., '30_days')
- **Deep Crawl Tags**: Automatically tagged with 'deep_crawl' and depth information

## API Integration
- **Bidirectional Mode**: Supports both server mode (hosting API) and client mode (forwarding to remote)
- **REST Endpoints**: Full REST API with authentication for all MCP tools
- **Configuration**: Uses `.env` file to switch between local and remote operation
- **Authentication**: API key-based authentication with rate limiting
- **Documentation**: Auto-generated OpenAPI docs at `/docs` endpoint
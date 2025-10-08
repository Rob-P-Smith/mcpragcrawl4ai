# AGENTS.md

This file provides guidance to Agents working with code in this repository.

## Project Overview
This is a Crawl4AI RAG (Retrieval-Augmented Generation) MCP Server implementation that provides web crawling capabilities with semantic search and knowledge base storage. The system consists of both MCP server and REST API components.

## Key Components

### Core Architecture
- **MCPServer**: Main server handling JSON-RPC 2.0 protocol for MCP communication
- **Crawl4AIRAG**: Web crawling interface that communicates with a local Crawl4AI service
- **RAGDatabase**: SQLite-based vector database using sqlite-vec extension for semantic search
- **Content Cleaner**: Navigation removal, boilerplate filtering, and chunk quality validation
- **Language Filter**: Automatic detection and filtering of non-English content using langdetect
- **RAM Database Mode**: In-memory SQLite database with differential sync for 10-50x faster queries
  - **Virtual Table Support**: Special handling for vec0 virtual tables with hard-coded schemas
  - **Dual Sync Strategy**: Idle sync (5s) + periodic sync (5min) for reliability
  - **Change Tracking**: Trigger-based tracking for regular tables, manual tracking for virtual tables
- **Error Logging**: Comprehensive error logging system writing to `crawl4ai_rag_errors.log`
- **API Gateway**: REST API layer with authentication and bidirectional communication support
- **Security Layer**: Input sanitization and SQL injection defense system (dbdefense.py)
- **Recrawl Utility**: Batch URL recrawling with concurrent processing and API-based execution

### Dependencies
- **External Service**: Requires Crawl4AI service running on `http://localhost:11235`
- **Vector Database**: Uses sqlite-vec extension for vector similarity search
- **ML Model**: Pre-loads SentenceTransformer 'all-MiniLM-L6-v2' for embeddings
- **Language Detection**: langdetect library for identifying and filtering non-English content
- **Key Libraries**: sqlite3, sqlite_vec, sentence_transformers, numpy, requests, fastapi, uvicorn, aiohttp, langdetect

### File Structure
- **core/rag_processor.py**: Main MCP server implementation and JSON-RPC handling
- **core/operations/crawler.py**: Web crawling logic with fit_markdown extraction and deep crawling functionality
- **core/data/storage.py**: Database operations, content storage, vector embeddings, and language filtering
- **core/data/content_cleaner.py**: Navigation removal, boilerplate filtering, and content quality validation
- **core/data/sync_manager.py**: RAM database synchronization manager with differential sync
- **core/data/dbdefense.py**: Security layer for input sanitization and SQL injection prevention
- **core/utilities/**: Helper scripts for testing and batch operations
  - **core/utilities/dbstats.py**: Database statistics and health monitoring
  - **core/utilities/batch_crawler.py**: Batch crawling with retry logic and progress tracking
  - **core/utilities/recrawl_utility.py**: Concurrent URL recrawling via API with rate limiting
- **api/**: REST API module for bidirectional communication
  - **api/api.py**: FastAPI server with all REST endpoints
  - **api/auth.py**: Authentication middleware and session management
- **deployments/**: Deployment configurations
  - **deployments/server/**: Server deployment (REST API + MCP server in Docker)
  - **deployments/client/**: Client deployment (lightweight MCP client forwarder)

### Database Schema
- **crawled_content**: Stores web content with metadata, retention policies, and session tracking
- **sessions**: Tracks user sessions for temporary content management
- **content_vectors**: Virtual table for vector embeddings using vec0 engine
  - Schema: `['rowid', 'embedding', 'content_id']` (rowid is implicit in vec0 tables)
  - Primary key: `content_id` (not `id` like regular tables)
  - Special handling required in sync operations due to virtual table limitations
- **blocked_domains**: Stores blocked domain patterns with wildcard support
- **_sync_tracker**: Shadow table for tracking RAM database changes (RAM mode only)
  - Tracks table_name, record_id, operation (INSERT/UPDATE/DELETE), timestamp
  - Cleared after successful sync to disk

## Available Tools

### Crawling Tools
1. **crawl_url**: Crawl without storing
2. **crawl_and_remember**: Crawl and store permanently
3. **crawl_temp**: Crawl and store temporarily (session-only)
4. **deep_crawl_dfs**: Deep crawl multiple pages using depth-first search without storing
5. **deep_crawl_and_store**: Deep crawl multiple pages using DFS and store all in knowledge base

### Search Tools
6. **search_memory**: Semantic search of stored content
   - Supports tag filtering via `tags` parameter (comma-separated, ANY match)
   - Results are automatically deduplicated by URL (keeps best match per URL)
   - Example: `search_memory(query="react hooks", tags="react, frontend", limit=10)`
7. **target_search**: Intelligent search with automatic tag expansion
   - Performs initial semantic search to discover tags
   - Re-searches using discovered tags to expand results
   - Deduplicates and ranks results by relevance
   - Returns discovered tags and expansion metadata
   - Example: `target_search(query="react hooks", initial_limit=5, expanded_limit=20)`

### Memory Management Tools
8. **list_memory**: List all stored content with optional filtering
9. **forget_url**: Remove specific content by URL
10. **clear_temp_memory**: Clear temporary session content

### Database Tools
11. **get_database_stats**: Get comprehensive database statistics
    - Returns record counts, storage breakdown, and recent activity
    - Includes `using_ram_db` flag to indicate if RAM or disk mode is active
    - Queries the actual database in use (RAM when in memory mode)
12. **list_domains**: List all unique domains with page counts

### Security Tools
13. **block_domain**: Block domains from being crawled (supports wildcards)
14. **unblock_domain**: Remove domain from blocklist
15. **list_blocked_domains**: View all blocked domain patterns

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

# Install API dependencies first
pip install -r requirements.txt
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

# Standalone Crawl4AI service (if needed)
docker run -d --name crawl4ai -p 11235:11235 unclecode/crawl4ai:latest
docker logs crawl4ai
docker stop crawl4ai
```

The server expects JSON-RPC 2.0 requests via stdin and responds via stdout. Errors are logged to both stderr and the log file.

## Deep Crawling Features
- **DFS Strategy**: Uses depth-first search to crawl multiple interconnected pages
- **Configurable Depth**: Control how many levels deep to crawl (max 5 levels)
- **Page Limits**: Restrict maximum pages crawled to prevent resource exhaustion (max 250 pages)
- **External Links**: Option to follow or ignore external domain links
- **URL Scoring**: Filter pages based on relevance scores (0.0-1.0 threshold)
- **Bulk Storage**: Store all discovered pages in the knowledge base with automatic tagging

## Data Persistence
- **Database**: SQLite file `crawl4ai_rag.db` in the working directory
- **Content Processing Pipeline**:
  1. Crawl4AI extracts content using fit_markdown (cleaner than raw_markdown)
  2. Content cleaner removes navigation, boilerplate, and low-quality content
  3. Language detection filters out non-English content
  4. Chunks are filtered to remove navigation-heavy segments
  5. Only quality content is stored and embedded
- **Content Chunking**: Text split into 500-word chunks with 50-word overlap
- **Storage Optimization**: 70-80% reduction in storage through intelligent cleaning
- **Retention Policies**: 'permanent', 'session_only', or time-based (e.g., '30_days')
- **Deep Crawl Tags**: Automatically tagged with 'deep_crawl' and depth information
- **Vector Embeddings**: 384-dimensional vectors using all-MiniLM-L6-v2 model
- **Markdown Storage**: fit_markdown format for better semantic search quality

## Environment Configuration

### Key Environment Variables
```bash
# RAM Database Mode (default: true)
USE_MEMORY_DB=true

# Server Mode (true = host API, false = forward to remote)
IS_SERVER=true

# API Configuration
API_PORT=8080
API_HOST=0.0.0.0

# Crawl4AI Service
CRAWL4AI_URL=http://localhost:11235

# Database Path
DB_PATH=/app/data/crawl4ai_rag.db

# Authentication
API_KEY=your-api-key-here
```

## Best Practices

### Performance Optimization
1. **Use RAM Database Mode**: Enable `USE_MEMORY_DB=true` for 10-50x faster queries
2. **Batch Operations**: Use batch crawler for bulk ingestion instead of individual crawls
3. **Tag Filtering**: Use specific tags in searches to reduce result set size
4. **Pagination**: Use limit/offset parameters to control memory usage

### Security
1. **Input Validation**: All inputs are automatically sanitized via dbdefense.py
2. **Domain Blocking**: Block untrusted or problematic domains before crawling
3. **API Authentication**: Always use API key authentication in production
4. **Rate Limiting**: Configure appropriate rate limits for your use case

### Content Management
1. **Retention Policies**: Use session_only for temporary data to avoid database bloat
2. **Regular Cleanup**: Periodically clear temp memory for long-running sessions
3. **Tag Organization**: Use consistent tagging strategy for better searchability
4. **Domain Monitoring**: Use list_domains to track content distribution

### Monitoring
1. **Database Stats**: Monitor `/api/v1/stats` for storage and performance metrics
2. **Sync Health**: Check `/api/v1/db/stats` for RAM sync status when using memory mode
3. **Error Logs**: Review `crawl4ai_rag_errors.log` for troubleshooting
4. **Blocked Domains**: Audit blocklist regularly via list_blocked_domains

## API Integration

### REST API Endpoints
The system provides a comprehensive REST API with the following endpoints:

#### Health & Status
- `GET /health` - Health check endpoint
- `GET /api/v1/help` - List all available tools with examples
- `GET /api/v1/status` - Server status and configuration

#### Crawling Endpoints
- `POST /api/v1/crawl` - Crawl URL without storing
- `POST /api/v1/crawl/store` - Crawl and store permanently
- `POST /api/v1/crawl/temp` - Crawl and store temporarily
- `POST /api/v1/crawl/deep/store` - Deep crawl and store multiple pages

#### Search Endpoints
- `POST /api/v1/search` - Semantic search with optional tag filtering
- `POST /api/v1/search/target` - Intelligent search with tag expansion

#### Memory Management
- `GET /api/v1/memory` - List stored content with pagination
- `DELETE /api/v1/memory` - Delete content by URL
- `DELETE /api/v1/memory/temp` - Clear temporary session content

#### Database & Statistics
- `GET /api/v1/stats` - Comprehensive database statistics
- `GET /api/v1/db/stats` - RAM database sync metrics and health
- `GET /api/v1/domains` - List all domains with page counts

#### Security & Blocking
- `GET /api/v1/blocked-domains` - List blocked domain patterns
- `POST /api/v1/blocked-domains` - Add domain to blocklist
- `DELETE /api/v1/blocked-domains` - Remove domain from blocklist

### API Features
- **Authentication**: API key-based authentication (Bearer token)
- **Rate Limiting**: Configurable rate limits per session
- **Bidirectional Mode**: Supports both server mode (hosting API) and client mode (forwarding to remote)
- **Configuration**: Uses `.env` file to switch between local and remote operation
- **Documentation**: Auto-generated OpenAPI docs at `/docs` endpoint
- **Error Handling**: Comprehensive error responses with detailed messages

## Client Mode Support
The system supports running in client mode where it forwards requests to a remote API server. This allows for distributed deployment scenarios where the MCP server runs separately from the API backend.

## RAM Database Mode
The system supports running the entire SQLite database in memory for significantly faster query performance (10-50x improvement):

### How It Works
- **Initialization**: On container startup, the entire disk database is loaded into RAM using SQLite's backup API
- **Differential Sync**: Only changed records are synced back to disk using a shadow table (`_sync_tracker`) with triggers
- **Dual Sync Strategy**:
  - **Idle Sync**: Syncs after 5 seconds of no write activity
  - **Periodic Sync**: Syncs every 5 minutes regardless of activity
- **Automatic Tracking**: Regular tables use SQLite triggers for automatic change detection
- **Manual Tracking**: Virtual tables (like `content_vectors`) use manual tracking since they don't support triggers

### Virtual Table Support
The sync manager includes special handling for sqlite-vec virtual tables:
- **Schema Registry**: Hard-coded schemas for virtual tables (PRAGMA table_info returns empty)
- **Primary Key Handling**: Uses `content_id` for content_vectors instead of `id`
- **Column Detection**: Includes implicit `rowid` column in vec0 virtual tables
- **Validation**: Checks for empty column lists to prevent sync failures

### Configuration
Set `USE_MEMORY_DB=true` in `.env` to enable RAM database mode. The system will:
- Load the entire database into `:memory:` on startup
- Track all changes via triggers and shadow table
- Sync changes to disk automatically (idle + periodic)
- Query stats show `using_ram_db: true` when active
- Sync metrics available in `/api/v1/stats` response

### Monitoring
- **Endpoint**: `/api/v1/stats` includes `sync_metrics` with full sync health data
- **Metrics**: Track total syncs, sync duration, failed syncs, records synced, and pending changes
- **Health**: Monitor pending changes, time since last sync, and sync success rate
- **Logs**: Check Docker logs for sync messages: `✅ Synced N changes to disk in Xs`

## Security Features

### Input Sanitization (dbdefense.py)
All user inputs are sanitized before database operations:
- **SQL Injection Defense**: Parameterized queries and strict input validation
- **URL Validation**: Protocol checking, domain validation, and blocked domain enforcement
- **String Sanitization**: Length limits, dangerous character removal, Unicode normalization
- **Type Coercion**: Integer, boolean, and pattern validation with safe defaults
- **Tag Sanitization**: Comma-separated tag lists with length and character restrictions
- **Blocked Domains**: Wildcard pattern matching to prevent crawling forbidden domains

### Content Filtering
- **Social Media Platforms**: Automatic blocking of major social media sites
- **Adult Content**: Detection and blocking of NSFW domains
- **Custom Blocklist**: User-defined domain patterns with wildcard support

## Batch Crawling

### Legacy Batch Crawler (batch_crawler.py)
The system includes a batch crawler utility with advanced features:
- **Progress Tracking**: Real-time progress bars and statistics
- **Retry Logic**: Automatic retry of failed URLs with configurable attempts
- **Concurrency Control**: Configurable concurrent request limits
- **Error Logging**: Detailed error tracking with failed URL collection
- **Resume Support**: Can restart from failed URLs only
- **Rate Limiting**: Respects server rate limits and backoff strategies

### Recrawl Utility (recrawl_utility.py)
Modern utility for recrawling existing URLs with improved architecture:
- **API-Based**: Uses REST API instead of direct database access to avoid sync conflicts
- **Concurrent Processing**: Async processing with semaphore-based rate limiting
- **Direct DB Read**: Reads URLs from disk database, sends crawl requests to API
- **Rate Limiting**: Configurable delay and concurrency (e.g., 10 concurrent, 60 req/min)
- **Dry-Run Mode**: Preview what will be recrawled before executing
- **Progress Tracking**: Real-time progress with success/failure statistics
- **Filter Support**: Filter by retention policy, tags, or URL patterns

#### Usage Examples
```bash
# Dry run to preview recrawl
python3 core/utilities/recrawl_utility.py --all --dry-run

# Recrawl all URLs with 10 concurrent requests, 0.6s delay (60 req/min)
python3 core/utilities/recrawl_utility.py --all --concurrent 10 --delay 0.6

# Recrawl specific retention policy
python3 core/utilities/recrawl_utility.py --policy permanent --concurrent 5 --delay 1.0

# Recrawl URLs with specific tags
python3 core/utilities/recrawl_utility.py --tags "react,documentation" --limit 100
```

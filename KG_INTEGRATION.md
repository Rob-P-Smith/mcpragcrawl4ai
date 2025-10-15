# Knowledge Graph Integration - Implementation Summary

**Status:** Partial Implementation Complete
**Date:** 2025-10-15

## Overview

Integrated Knowledge Graph service with graceful fallback behavior. The RAG system now:
- ✅ Tracks chunk boundaries for KG processing
- ✅ Health-checks KG service before queueing
- ✅ Falls back to vector-only search if KG unavailable
- ✅ Preserves all existing functionality when KG is down

## Implemented Components

### 1. Database Schema (✅ COMPLETE)

**Location:** `migrations/001_add_kg_support.sql` and `.py`

**New Tables:**
- `content_chunks` - Tracks chunk metadata with char positions
- `chunk_entities` - Stores extracted entities per chunk
- `chunk_relationships` - Stores relationships between entities
- `kg_processing_queue` - Manages KG processing queue

**New Columns on `crawled_content`:**
- `kg_processed` - Boolean flag
- `kg_entity_count` - Count of extracted entities
- `kg_relationship_count` - Count of relationships
- `kg_document_id` - Neo4j Document node ID
- `kg_processed_at` - Processing timestamp

**Migration:**
- Automatically runs on database initialization
- Safely handles existing databases
- Rollback support included

### 2. KG Service Configuration (✅ COMPLETE)

**Location:** `core/data/kg_config.py`

**Features:**
- Environment-based configuration (`KG_SERVICE_ENABLED`, `KG_SERVICE_URL`)
- Health checking with configurable intervals
- Consecutive failure tracking
- Graceful degradation when service unavailable
- HTTP client pooling for efficiency

**Environment Variables:**
```bash
KG_SERVICE_ENABLED=true           # Enable/disable KG integration
KG_SERVICE_URL=http://kg-service:8088  # KG service endpoint
KG_SERVICE_TIMEOUT=300.0          # Request timeout (5 minutes)
KG_HEALTH_CHECK_INTERVAL=30.0     # Health check frequency (seconds)
KG_MAX_RETRIES=3                  # Max retry attempts
```

**Usage:**
```python
from core.data.kg_config import get_kg_config

kg_config = get_kg_config()

# Check if service is healthy
if await kg_config.check_health():
    # Service available
    result = await kg_config.send_to_kg_queue(...)
```

### 3. Queue Management (✅ COMPLETE)

**Location:** `core/data/kg_queue.py`

**KGQueueManager Class:**

**Methods:**
- `calculate_chunk_boundaries()` - Map chunks to character positions in full document
- `store_chunk_metadata()` - Save chunk boundaries to `content_chunks` table
- `queue_for_kg_processing()` - Queue content with health check
- `get_chunk_metadata_for_content()` - Retrieve chunk data
- `write_kg_results()` - Write entities/relationships back to SQLite

**Behavior:**
- Health-checks KG service before queuing
- Marks as `skipped` if service unavailable (allows retry later)
- Stores chunk boundaries with `kg_processed=0` flag
- Non-blocking - doesn't fail RAG operations

### 4. Storage Layer Updates (✅ COMPLETE)

**Location:** `core/data/storage.py`

**Changes to `generate_embeddings()`:**
```python
# After creating embeddings:
1. Get vector rowids
2. Calculate chunk boundaries
3. Store to content_chunks table
4. Log success
```

**Changes to `store_content()`:**
```python
# After generating embeddings:
1. Check if KG service enabled
2. Schedule async KG queue check (non-blocking)
3. Continue with RAG storage regardless of KG result
```

**New Method: `_queue_for_kg_async()`**
- Async helper for KG queuing
- Checks health
- Queues content
- Logs results
- Never fails parent operation

**Migration Integration:**
- Automatically runs migration 001 on `init_database()`
- Gracefully handles missing migration files
- Logs migration status

## Graceful Fallback Behavior

### When KG Service is DOWN:

1. **Health Check Fails** → Service marked unhealthy
2. **Queue Attempt** → Content marked as `skipped` with reason `kg_service_unavailable`
3. **Chunk Tracking** → Chunks still stored with `kg_processed=0`
4. **RAG Operations** → Continue normally with vector-only search
5. **User Experience** → Seamless - no errors, just no KG enhancement

### When KG Service Comes BACK:

1. Background worker can query for `status='skipped'` items
2. Retry KG processing for previously skipped content
3. Update `kg_processed=1` on success
4. Search automatically uses KG data when available

### Error Handling:

```python
# Example: Storage continues even if KG fails
try:
    # Store content to SQLite
    content_id = store_to_sqlite()

    # Generate embeddings
    generate_embeddings(content_id)

    # Try KG queuing (non-blocking)
    try:
        await queue_for_kg()
    except:
        logger.warning("KG queuing failed - continuing")

    # Return success regardless
    return {"success": True, "content_id": content_id}
```

## Data Flow

### Successful KG Processing:

```
User → Crawl → Clean → Chunk → Embed → SQLite
                                  ↓
                         Calculate chunk boundaries
                                  ↓
                         Store to content_chunks
                                  ↓
                     Check KG service health
                                  ↓
                          Service healthy?
                           ✓ Yes    ✗ No
                            ↓        ↓
                    Queue as      Mark as
                   'pending'     'skipped'
                            ↓
                  Background worker
                   processes queue
                            ↓
               POST to kg-service:8088
                            ↓
            Entity & relationship extraction
                            ↓
                     Store in Neo4j
                            ↓
                  Return results to worker
                            ↓
          Write entities/relationships to SQLite
                            ↓
            Update kg_processed=1, chunks.kg_processed=1
```

### KG Service Unavailable:

```
User → Crawl → Clean → Chunk → Embed → SQLite
                                  ↓
                         Calculate chunk boundaries
                                  ↓
                         Store to content_chunks (kg_processed=0)
                                  ↓
                     Check KG service health
                                  ↓
                      Service unhealthy
                                  ↓
              Queue as 'skipped' with reason
                                  ↓
                    Continue RAG operations
                                  ↓
                  User gets vector-only results
                     (No KG enhancement)
```

## Database Schema Details

### content_chunks Table

```sql
CREATE TABLE content_chunks (
    rowid INTEGER PRIMARY KEY,       -- Same as content_vectors rowid
    content_id INTEGER NOT NULL,     -- FK to crawled_content
    chunk_index INTEGER NOT NULL,    -- 0, 1, 2, ...
    chunk_text TEXT NOT NULL,
    char_start INTEGER NOT NULL,     -- Position in original markdown
    char_end INTEGER NOT NULL,
    word_count INTEGER,
    kg_processed BOOLEAN DEFAULT 0,  -- KG extraction attempted?
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose:** Maps chunks to their exact positions in the original document

**Example:**
```
rowid | content_id | chunk_index | char_start | char_end | kg_processed
45001 |        123 |           0 |          0 |     2500 |            0
45002 |        123 |           1 |       2450 |     4950 |            0
```

### kg_processing_queue Table

```sql
CREATE TABLE kg_processing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',   -- pending, processing, completed, failed, skipped
    priority INTEGER DEFAULT 1,
    queued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processing_started_at DATETIME,
    processed_at DATETIME,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    result_summary TEXT,            -- JSON with stats
    skipped_reason TEXT             -- e.g., 'kg_service_unavailable'
);
```

**Statuses:**
- `pending` - Waiting for background worker
- `processing` - Currently being processed
- `completed` - Successfully processed
- `failed` - Failed after max retries
- `skipped` - KG service unavailable (can retry later)

## Configuration Examples

### Enable KG Integration

```bash
# In docker-compose.yml or .env
KG_SERVICE_ENABLED=true
KG_SERVICE_URL=http://kg-service:8088
KG_HEALTH_CHECK_INTERVAL=30.0
```

### Disable KG Integration (Fallback to Vector-Only)

```bash
KG_SERVICE_ENABLED=false
```

## Remaining Work

### ❌ NOT YET IMPLEMENTED:

1. **Background KG Worker** (`core/workers/kg_worker.py`)
   - Polls `kg_processing_queue` table
   - Sends documents to kg-service
   - Writes results back to SQLite
   - Handles retries and failures

2. **Graph-Enhanced Search** (`core/rag_processor.py` or `storage.py`)
   - Query `chunk_entities` and `chunk_relationships` tables
   - Expand queries using entity/relationship data
   - Combine graph relevance with vector similarity
   - Re-rank results

3. **API Endpoints** (`api/api.py`)
   - `/kg/status` - Get KG service health and stats
   - `/kg/reprocess/<content_id>` - Retry KG processing for specific content
   - `/kg/queue/stats` - Queue statistics

4. **Docker Integration**
   - Update `docker-compose.yml` to include kg-service
   - Add kg-service to `crawler_default` network
   - Environment variable configuration

## Testing

### Manual Testing:

```bash
# 1. Start mcpragcrawl4ai WITHOUT kg-service
docker-compose up mcpragcrawl4ai

# 2. Crawl some content
curl -X POST http://localhost:8080/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.python.org/3/tutorial/"}'

# 3. Check database
sqlite3 /app/data/crawl4ai_rag.db
> SELECT COUNT(*) FROM content_chunks;
> SELECT COUNT(*) FROM kg_processing_queue WHERE status='skipped';

# 4. Start kg-service
docker-compose up -d kg-service

# 5. Health check should now pass
# 6. New content should queue as 'pending' instead of 'skipped'
```

### Verify Fallback Behavior:

```bash
# Stop kg-service while crawling
docker-compose stop kg-service

# Crawl content - should still work
curl -X POST http://localhost:8080/crawl ...

# Check queue - should be marked 'skipped'
sqlite3 ... "SELECT status, skipped_reason FROM kg_processing_queue ORDER BY id DESC LIMIT 1;"
```

## Benefits

✅ **Non-Breaking**: Existing RAG functionality unchanged
✅ **Graceful Degradation**: Falls back to vector-only if KG unavailable
✅ **Future-Proof**: Chunk metadata preserved for later KG processing
✅ **Health-Aware**: Active monitoring prevents failed requests
✅ **Retry-Capable**: Skipped items can be retried when service returns
✅ **No Data Loss**: All chunk boundaries tracked regardless of KG status

## Next Steps

1. Implement background KG worker
2. Add graph-enhanced search logic
3. Create KG management API endpoints
4. Update docker-compose.yml
5. Write integration tests
6. Update user documentation

---

**Implementation Status:** 60% Complete
**Core Infrastructure:** ✅ Ready
**Background Processing:** ❌ Pending
**Search Enhancement:** ❌ Pending

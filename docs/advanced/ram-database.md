# RAM Database Mode

## Overview

The Crawl4AI RAG MCP Server features an advanced RAM database mode that dramatically improves performance by keeping the entire database in memory while maintaining data persistence through intelligent differential synchronization to disk.

## Architecture

### Components

The RAM database system consists of three key components:

1. **DBSyncManager** (`core/data/sync_manager.py`) - Manages synchronization between RAM and disk
2. **RAGDatabase** (`core/data/storage.py`) - Database operations with RAM mode support
3. **Sync Tracking System** - Monitors changes and triggers synchronization

### How It Works

```
┌─────────────────────────────────────────┐
│         Application Layer               │
│  (core/data/storage.py - RAGDatabase)  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      In-Memory SQLite Database          │
│         (:memory: connection)           │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  _sync_tracker (shadow table)     │  │
│  │  - Tracks INSERT/UPDATE/DELETE    │  │
│  │  - Records timestamp and operation│  │
│  └───────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       DBSyncManager                     │
│  (core/data/sync_manager.py)           │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Idle Sync Monitor              │   │
│  │  - Waits 5s after last write    │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Periodic Sync Monitor          │   │
│  │  - Syncs every 5 minutes        │   │
│  └─────────────────────────────────┘   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Disk SQLite Database               │
│    (crawl4ai_rag.db file)               │
└─────────────────────────────────────────┘
```

## Configuration

### Enabling RAM Database Mode

Set the environment variable in your `.env` file:

```bash
# Enable RAM database mode (default: true)
USE_MEMORY_DB=true

# Disable RAM database mode (use traditional disk mode)
USE_MEMORY_DB=false
```

### Initialization

The RAM database is initialized automatically on application startup:

```python
# From core/data/storage.py
async def initialize_async(self):
    """
    Initialize memory database (called from start_api_server.py on startup)
    Only needed when USE_MEMORY_DB=true
    """
    if self.sync_manager and self.db is None:
        self.db = await self.sync_manager.initialize()
        self.init_database()  # Create tables if needed in memory
        print("✅ RAM Database initialized and ready")
```

## Synchronization Strategy

### Differential Sync

The system uses differential synchronization to only sync changed records:

1. **Change Tracking**: Database triggers automatically track all INSERT, UPDATE, and DELETE operations in the `_sync_tracker` table
2. **Idle Detection**: After 5 seconds of no write activity, pending changes are synced to disk **once** (prevented from repeating by `idle_sync_completed` flag)
3. **Periodic Sync**: Every 5 minutes, any pending changes are synced regardless of idle time
4. **Batch Processing**: Changes are grouped by table and synced in batches for efficiency
5. **Write Detection**: Any new write resets the `idle_sync_completed` flag, allowing the next idle sync to occur

### Idle Sync Optimization

To prevent redundant disk writes when the system is mostly idle, the sync manager uses an `idle_sync_completed` boolean flag:

- **On New Write**: Flag is set to `false`, idle timer starts
- **After 5s Idle**: If changes pending and flag is `false`, sync occurs and flag is set to `true`
- **While Idle**: Further idle checks skip syncing since flag is `true`
- **On Next Write**: Flag resets to `false`, cycle repeats

This ensures the disk is updated **once** after each burst of writes, not continuously while idle.

### Sync Triggers

The `_sync_tracker` table and triggers are created automatically:

```python
# From core/data/sync_manager.py - _create_sync_tracker()
CREATE TABLE IF NOT EXISTS _sync_tracker (
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    operation TEXT NOT NULL,
    timestamp REAL NOT NULL,
    PRIMARY KEY (table_name, record_id)
)

# Triggers track changes automatically
CREATE TRIGGER track_content_insert
AFTER INSERT ON crawled_content
BEGIN
    INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
    VALUES ('crawled_content', NEW.id, 'INSERT', strftime('%s', 'now'));
END
```

### Vector Table Sync

Since `content_vectors` is a virtual table (sqlite-vec), triggers cannot be used. Instead, vector changes are tracked manually:

```python
# From core/data/sync_manager.py
async def track_vector_change(self, content_id: int, operation: str = 'INSERT'):
    """
    Manually track content_vectors changes (can't use triggers on virtual tables)

    Args:
        content_id: The content_id from crawled_content table
        operation: 'INSERT', 'UPDATE', or 'DELETE'
    """
    self.memory_conn.execute("""
        INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
        VALUES ('content_vectors', ?, ?, strftime('%s', 'now'))
    """, (content_id, operation))
```

## Sync Process Details

### Idle Sync Monitor

Runs continuously in the background:

```python
# From core/data/sync_manager.py
async def _idle_sync_monitor(self):
    """
    Background task: monitor for idle state and sync

    Runs forever:
    1. Sleep for 1 second
    2. Check if (current_time - last_write_time) > 5 seconds
    3. If yes and changes pending → trigger sync
    4. Repeat
    """
    while True:
        await asyncio.sleep(1)

        if self.last_write_time is None or self.is_syncing:
            continue

        idle_time = time.time() - self.last_write_time

        # Check if we have pending changes
        pending = self.memory_conn.execute(
            "SELECT COUNT(*) FROM _sync_tracker"
        ).fetchone()[0]

        if idle_time >= 5.0 and pending > 0:
            await self.differential_sync()
```

### Periodic Sync Monitor

Ensures data is synced at regular intervals:

```python
# From core/data/sync_manager.py
async def _periodic_sync_monitor(self):
    """
    Background task: periodic sync every 5 minutes
    """
    while True:
        await asyncio.sleep(300)  # 5 minutes

        if self.is_syncing:
            continue

        pending = self.memory_conn.execute(
            "SELECT COUNT(*) FROM _sync_tracker"
        ).fetchone()[0]

        if pending > 0:
            await self.differential_sync()
```

### Differential Sync Implementation

```python
# From core/data/sync_manager.py
async def differential_sync(self):
    """
    Sync only changed records from memory to disk

    Process:
    1. Acquire sync_lock (prevent concurrent syncs)
    2. Open disk connection
    3. Get all pending changes from _sync_tracker
    4. For each change:
       - INSERT/UPDATE: fetch from memory, write to disk
       - DELETE: remove from disk
    5. Commit disk transaction
    6. Clear _sync_tracker
    7. Update metrics
    8. Close disk connection
    """
    async with self.sync_lock:
        self.is_syncing = True

        # Get pending changes
        pending_changes = self.memory_conn.execute("""
            SELECT table_name, record_id, operation
            FROM _sync_tracker
            ORDER BY timestamp ASC
        """).fetchall()

        # Group by table for batch processing
        changes_by_table = {}
        for table_name, record_id, operation in pending_changes:
            if table_name not in changes_by_table:
                changes_by_table[table_name] = []
            changes_by_table[table_name].append((record_id, operation))

        # Process each table
        for table_name, changes in changes_by_table.items():
            await self._sync_table(disk_conn, table_name, changes)

        # Commit and clear tracker
        disk_conn.commit()
        self.memory_conn.execute("DELETE FROM _sync_tracker")
        self.memory_conn.commit()
```

## Monitoring

### Sync Metrics

The system tracks comprehensive sync metrics:

```python
# From core/data/sync_manager.py
self.metrics = {
    'total_syncs': 0,              # Total number of syncs performed
    'last_sync_time': None,        # Timestamp of last sync
    'last_sync_duration': 0,       # Duration of last sync in seconds
    'total_records_synced': 0,     # Cumulative records synced
    'failed_syncs': 0,             # Number of failed sync attempts
    'pending_changes': 0           # Current pending changes count
}
```

### API Endpoint for Metrics

Get real-time sync statistics via the REST API:

```bash
GET /api/v1/db/stats

# Response
{
  "success": true,
  "mode": "memory",
  "disk_db_path": "/app/data/crawl4ai_rag.db",
  "disk_db_size_mb": 45.23,
  "sync_metrics": {
    "total_syncs": 127,
    "last_sync_time": 1696534821.23,
    "last_sync_duration": 0.15,
    "total_records_synced": 3456,
    "failed_syncs": 0,
    "pending_changes": 0
  },
  "health": {
    "pending_changes": 0,
    "last_sync_ago_seconds": 12.5,
    "sync_success_rate": 1.0
  }
}
```

### Database Statistics

Get comprehensive database stats:

```python
# From core/data/storage.py
def get_database_stats(self) -> Dict[str, Any]:
    """Get comprehensive database statistics"""
    if self.is_memory_mode and self.db is not None:
        # Query RAM database directly
        return self._get_stats_from_ram_db()
    else:
        # Query disk database via dbstats module
        from core.utilities.dbstats import get_db_stats_dict
        stats = get_db_stats_dict(self.db_path)
        stats['using_ram_db'] = False
        return stats
```

## Performance Benefits

### Read Performance

- **10-100x faster** reads compared to disk-based SQLite
- No disk I/O latency for queries
- Instant vector similarity searches
- Optimal for high-frequency read operations

### Write Performance

- **5-10x faster** writes to memory
- Async sync doesn't block application
- Batch sync operations reduce disk writes
- Reduced wear on SSDs

### Memory Usage

- Typical database size: 50-500 MB in memory
- Vector embeddings: ~1.5 KB per page (384-dim float32)
- Reasonable for modern systems with 4GB+ RAM

## Best Practices

### 1. Monitor Pending Changes

Check pending changes regularly to ensure sync is working:

```bash
# Via API
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/db/stats
```

### 2. Graceful Shutdown

Ensure all pending changes are synced before shutdown:

```python
# Force sync before shutdown
if GLOBAL_DB.sync_manager:
    await GLOBAL_DB.sync_manager.differential_sync()
```

### 3. Backup Strategy

- Disk database is automatically updated via sync
- Regular backups of disk database recommended
- Sync happens automatically before most application shutdowns

### 4. Error Handling

The system logs all sync errors:

```python
except Exception as e:
    print(f"❌ Sync failed: {e}")
    self.metrics['failed_syncs'] += 1
    if 'disk_conn' in locals():
        disk_conn.rollback()
        disk_conn.close()
```

## Disk Mode Fallback

If RAM mode is disabled or fails, the system automatically falls back to traditional disk mode:

```python
# From core/data/storage.py
self.is_memory_mode = os.getenv("USE_MEMORY_DB", "true").lower() == "true"

if self.is_memory_mode:
    print("🚀 RAM Database mode enabled")
    self.sync_manager = DBSyncManager(db_path)
else:
    print("💾 Disk Database mode (traditional)")
    self.init_database()
```

## Troubleshooting

### Issue: Pending Changes Not Syncing

**Check:**
1. Verify sync monitors are running (check logs for startup messages)
2. Check `pending_changes` count in metrics
3. Look for sync errors in application logs

**Solution:**
```python
# Force a manual sync
await GLOBAL_DB.sync_manager.differential_sync()
```

### Issue: High Memory Usage

**Check:**
1. Database size: `GET /api/v1/stats`
2. Number of stored pages
3. Vector embeddings count

**Solution:**
- Clean up old content with retention policies
- Reduce vector dimensions (requires code change)
- Increase system RAM

### Issue: Sync Taking Too Long

**Check:**
1. `last_sync_duration` in metrics
2. Number of pending changes
3. Disk I/O performance

**Solution:**
- Reduce sync frequency (increase idle timeout)
- Use faster storage (SSD recommended)
- Optimize database indices

## Advanced Configuration

### Tuning Sync Intervals

Modify sync timing in `core/data/sync_manager.py`:

```python
# Idle sync timeout (default: 5 seconds)
if idle_time >= 5.0 and pending > 0:
    await self.differential_sync()

# Periodic sync interval (default: 300 seconds / 5 minutes)
await asyncio.sleep(300)
```

### Custom Sync Triggers

You can manually trigger sync operations:

```python
# Track a write operation
await GLOBAL_DB.sync_manager.track_write('crawled_content')

# Track a vector change
await GLOBAL_DB.sync_manager.track_vector_change(content_id, 'INSERT')

# Force immediate sync
await GLOBAL_DB.sync_manager.differential_sync()
```

## References

- **Implementation**: `/home/robiloo/Documents/mcpragcrawl4ai/core/data/sync_manager.py`
- **Integration**: `/home/robiloo/Documents/mcpragcrawl4ai/core/data/storage.py`
- **API Endpoint**: `/home/robiloo/Documents/mcpragcrawl4ai/api/api.py` (GET /api/v1/db/stats)

## See Also

- [Database Statistics](../guides/troubleshooting.md#database-issues)
- [Performance Optimization](../guides/deployment.md#performance-considerations)
- [API Reference](../api/endpoints.md)

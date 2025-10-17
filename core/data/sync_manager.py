import sqlite3
import asyncio
import time
import os
import sys
from typing import Optional
from pathlib import Path
import sqlite_vec


class DBSyncManager:
    """
    Manages synchronization between in-memory SQLite database and disk persistence

    Features:
    - Loads disk DB into memory on startup
    - Tracks all write operations
    - Syncs to disk after 5 seconds of idle time
    - Periodic sync every 5 minutes
    - Differential sync (only changed records)
    """

    def __init__(self, disk_path: str):
        self.disk_path = disk_path
        self.memory_conn: Optional[sqlite3.Connection] = None
        self.last_write_time: Optional[float] = None
        self.sync_lock = asyncio.Lock()
        self.is_syncing = False
        self.idle_sync_completed = False  # Track if idle sync already done since last write

        # Metrics
        self.metrics = {
            'total_syncs': 0,
            'last_sync_time': None,
            'last_sync_duration': 0,
            'total_records_synced': 0,
            'failed_syncs': 0,
            'pending_changes': 0
        }

    async def initialize(self) -> sqlite3.Connection:
        """
        Load disk DB into memory on startup

        Steps:
        1. Connect to disk DB at self.disk_path
        2. Create in-memory DB connection (:memory:)
        3. Use SQLite backup API to copy disk → memory
        4. Create sync tracking table and triggers
        5. Start background sync tasks
        6. Return memory connection for use by storage.py
        """
        print(f"🚀 Loading database from disk: {self.disk_path}")

        # Check if disk DB exists
        disk_path_obj = Path(self.disk_path)
        if not disk_path_obj.exists():
            print(f"⚠️  Disk database not found at {self.disk_path}, will create new")
            # Create empty disk DB first
            disk_conn = sqlite3.connect(self.disk_path)
            disk_conn.close()

        # Open disk connection
        disk_conn = sqlite3.connect(self.disk_path)

        # Create memory connection
        self.memory_conn = sqlite3.connect(':memory:', check_same_thread=False)

        # Load vec0 extension on memory connection BEFORE backup
        package_dir = os.path.dirname(sqlite_vec.__file__)
        extension_path = os.path.join(package_dir, 'vec0.so')
        self.memory_conn.enable_load_extension(True)
        self.memory_conn.load_extension(extension_path)

        # Copy entire disk DB to memory using backup API
        print("📦 Copying database to memory...")
        disk_conn.backup(self.memory_conn)

        # Close disk connection (we'll reopen for syncs)
        disk_conn.close()

        print("✅ Database loaded into memory")

        # Create sync tracking infrastructure
        self._create_sync_tracker()

        # Start background sync tasks
        asyncio.create_task(self._idle_sync_monitor())
        asyncio.create_task(self._periodic_sync_monitor())

        print("🔄 Sync monitors started (idle: 5s, periodic: 5min)")

        # TEST: Check if vec0 can be loaded for disk sync
        print("🧪 Testing vec0 extension loading for disk sync...", file=sys.stderr, flush=True)
        try:
            test_conn = sqlite3.connect(self.disk_path, check_same_thread=False)
            package_dir = os.path.dirname(sqlite_vec.__file__)
            extension_path = os.path.join(package_dir, 'vec0.so')
            print(f"   Extension path: {extension_path}", file=sys.stderr, flush=True)
            print(f"   File exists: {os.path.exists(extension_path)}", file=sys.stderr, flush=True)
            test_conn.enable_load_extension(True)
            test_conn.load_extension(extension_path)
            print("✅ vec0 extension test PASSED - sync should work", file=sys.stderr, flush=True)
            test_conn.close()
        except Exception as e:
            print(f"❌ vec0 extension test FAILED: {e}", file=sys.stderr, flush=True)
            print(f"   WARNING: Disk sync will fail!", file=sys.stderr, flush=True)

        return self.memory_conn

    def _create_sync_tracker(self):
        """
        Create shadow table and triggers to track changes

        Tracks:
        - Which records were inserted/updated/deleted
        - Timestamp of change
        - Allows differential sync (only changed records)
        """
        # Create tracker table
        self.memory_conn.execute("""
            CREATE TABLE IF NOT EXISTS _sync_tracker (
                table_name TEXT NOT NULL,
                record_id INTEGER NOT NULL,
                operation TEXT NOT NULL,
                timestamp REAL NOT NULL,
                PRIMARY KEY (table_name, record_id)
            )
        """)

        # Triggers for crawled_content table
        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_content_insert
            AFTER INSERT ON crawled_content
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('crawled_content', NEW.id, 'INSERT', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_content_update
            AFTER UPDATE ON crawled_content
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('crawled_content', NEW.id, 'UPDATE', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_content_delete
            AFTER DELETE ON crawled_content
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('crawled_content', OLD.id, 'DELETE', strftime('%s', 'now'));
            END
        """)

        # NOTE: Cannot create triggers on content_vectors because it's a virtual table (sqlite-vec)
        # content_vectors changes will be tracked via manual track_vector_change() calls

        # ====================================================================
        # Triggers for KG tables
        # ====================================================================

        # content_chunks triggers
        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_chunks_insert
            AFTER INSERT ON content_chunks
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('content_chunks', NEW.rowid, 'INSERT', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_chunks_update
            AFTER UPDATE ON content_chunks
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('content_chunks', NEW.rowid, 'UPDATE', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_chunks_delete
            AFTER DELETE ON content_chunks
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('content_chunks', OLD.rowid, 'DELETE', strftime('%s', 'now'));
            END
        """)

        # chunk_entities triggers
        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_entities_insert
            AFTER INSERT ON chunk_entities
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('chunk_entities', NEW.id, 'INSERT', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_entities_update
            AFTER UPDATE ON chunk_entities
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('chunk_entities', NEW.id, 'UPDATE', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_entities_delete
            AFTER DELETE ON chunk_entities
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('chunk_entities', OLD.id, 'DELETE', strftime('%s', 'now'));
            END
        """)

        # chunk_relationships triggers
        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_relationships_insert
            AFTER INSERT ON chunk_relationships
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('chunk_relationships', NEW.id, 'INSERT', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_relationships_update
            AFTER UPDATE ON chunk_relationships
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('chunk_relationships', NEW.id, 'UPDATE', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_relationships_delete
            AFTER DELETE ON chunk_relationships
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('chunk_relationships', OLD.id, 'DELETE', strftime('%s', 'now'));
            END
        """)

        # kg_processing_queue triggers
        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_queue_insert
            AFTER INSERT ON kg_processing_queue
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('kg_processing_queue', NEW.id, 'INSERT', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_queue_update
            AFTER UPDATE ON kg_processing_queue
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('kg_processing_queue', NEW.id, 'UPDATE', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_queue_delete
            AFTER DELETE ON kg_processing_queue
            BEGIN
                INSERT OR REPLACE INTO _sync_tracker (table_name, record_id, operation, timestamp)
                VALUES ('kg_processing_queue', OLD.id, 'DELETE', strftime('%s', 'now'));
            END
        """)

        self.memory_conn.commit()
        print("✅ Sync tracking triggers created (crawled_content + KG tables)")

    async def track_write(self, table_name: str):
        """
        Called by storage.py after any write operation

        Simply updates the last write timestamp for idle detection
        The actual change tracking is handled by triggers for regular tables
        """
        self.last_write_time = time.time()
        self.idle_sync_completed = False  # Reset flag on new write

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
        self.memory_conn.commit()
        self.last_write_time = time.time()
        self.idle_sync_completed = False  # Reset flag on new write

    async def _idle_sync_monitor(self):
        """
        Background task: monitor for idle state and sync

        Runs forever:
        1. Sleep for 1 second
        2. Check if (current_time - last_write_time) > 5 seconds
        3. If yes and changes pending and not already synced → trigger sync
        4. Repeat

        Uses idle_sync_completed flag to prevent redundant syncs.
        Flag is reset on new writes, preventing constant disk updates when idle.
        """
        while True:
            await asyncio.sleep(1)

            if self.last_write_time is None or self.is_syncing:
                continue

            # Skip if idle sync already completed since last write
            if self.idle_sync_completed:
                continue

            idle_time = time.time() - self.last_write_time

            # Check if we have pending changes
            pending = self.memory_conn.execute(
                "SELECT COUNT(*) FROM _sync_tracker"
            ).fetchone()[0]

            self.metrics['pending_changes'] = pending

            if idle_time >= 5.0 and pending > 0:
                print(f"💤 Idle detected ({idle_time:.1f}s), syncing {pending} changes to disk...")
                await self.differential_sync()
                self.idle_sync_completed = True  # Mark idle sync as completed

    async def _periodic_sync_monitor(self):
        """
        Background task: periodic sync every 5 minutes

        Runs forever:
        1. Sleep for 300 seconds (5 minutes)
        2. If changes pending → trigger sync
        3. Repeat
        """
        while True:
            await asyncio.sleep(300)  # 5 minutes

            if self.is_syncing:
                continue

            # Check if we have pending changes
            pending = self.memory_conn.execute(
                "SELECT COUNT(*) FROM _sync_tracker"
            ).fetchone()[0]

            if pending > 0:
                print(f"⏰ Periodic sync (5 min), syncing {pending} changes to disk...")
                await self.differential_sync()

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
        if self.is_syncing:
            return

        async with self.sync_lock:
            self.is_syncing = True
            start_time = time.time()

            try:
                # Open disk connection (check_same_thread=False needed for extension loading)
                disk_conn = sqlite3.connect(self.disk_path, check_same_thread=False)

                # Load sqlite-vec extension IMMEDIATELY (disk DB has vec0 tables)
                package_dir = os.path.dirname(sqlite_vec.__file__)
                extension_path = os.path.join(package_dir, 'vec0.so')

                print(f"🔍 DEBUG: About to load vec0 extension", file=sys.stderr, flush=True)
                print(f"   sqlite_vec.__file__: {sqlite_vec.__file__}", file=sys.stderr, flush=True)
                print(f"   Extension path: {extension_path}", file=sys.stderr, flush=True)
                print(f"   File exists: {os.path.exists(extension_path)}", file=sys.stderr, flush=True)

                disk_conn.enable_load_extension(True)
                disk_conn.load_extension(extension_path)
                print(f"✅ Extension loaded successfully", file=sys.stderr, flush=True)

                disk_conn.execute("PRAGMA journal_mode=WAL")
                disk_conn.execute("PRAGMA synchronous=NORMAL")

                # Get all pending changes
                pending_changes = self.memory_conn.execute("""
                    SELECT table_name, record_id, operation
                    FROM _sync_tracker
                    ORDER BY timestamp ASC
                """).fetchall()

                if not pending_changes:
                    disk_conn.close()
                    self.is_syncing = False
                    return

                # Group changes by table for batch processing
                changes_by_table = {}
                for table_name, record_id, operation in pending_changes:
                    if table_name not in changes_by_table:
                        changes_by_table[table_name] = []
                    changes_by_table[table_name].append((record_id, operation))

                # Process crawled_content changes
                if 'crawled_content' in changes_by_table:
                    await self._sync_table(
                        disk_conn,
                        'crawled_content',
                        changes_by_table['crawled_content']
                    )

                # Process content_vectors changes
                if 'content_vectors' in changes_by_table:
                    await self._sync_table(
                        disk_conn,
                        'content_vectors',
                        changes_by_table['content_vectors']
                    )

                # Process KG table changes
                if 'content_chunks' in changes_by_table:
                    await self._sync_table(
                        disk_conn,
                        'content_chunks',
                        changes_by_table['content_chunks']
                    )

                if 'chunk_entities' in changes_by_table:
                    await self._sync_table(
                        disk_conn,
                        'chunk_entities',
                        changes_by_table['chunk_entities']
                    )

                if 'chunk_relationships' in changes_by_table:
                    await self._sync_table(
                        disk_conn,
                        'chunk_relationships',
                        changes_by_table['chunk_relationships']
                    )

                if 'kg_processing_queue' in changes_by_table:
                    await self._sync_table(
                        disk_conn,
                        'kg_processing_queue',
                        changes_by_table['kg_processing_queue']
                    )

                # Commit all changes
                disk_conn.commit()

                # Clear sync tracker
                self.memory_conn.execute("DELETE FROM _sync_tracker")
                self.memory_conn.commit()

                # Update metrics
                duration = time.time() - start_time
                self.metrics['total_syncs'] += 1
                self.metrics['last_sync_time'] = time.time()
                self.metrics['last_sync_duration'] = duration
                self.metrics['total_records_synced'] += len(pending_changes)
                self.metrics['pending_changes'] = 0

                print(f"✅ Synced {len(pending_changes)} changes to disk in {duration:.2f}s")

                disk_conn.close()

            except Exception as e:
                print(f"❌ Sync failed: {e}")
                self.metrics['failed_syncs'] += 1
                if 'disk_conn' in locals():
                    disk_conn.rollback()
                    disk_conn.close()
            finally:
                self.is_syncing = False

    async def _sync_table(self, disk_conn: sqlite3.Connection, table_name: str, changes: list):
        """
        Sync changes for a specific table

        Args:
            disk_conn: Open connection to disk database
            table_name: Name of table to sync
            changes: List of (record_id, operation) tuples
        """
        # Schema registry for virtual tables that don't support PRAGMA table_info
        # Maps table_name -> (columns, primary_key_column)
        # Note: vec0 virtual tables have an implicit 'rowid' column that comes first in SELECT *
        VIRTUAL_TABLE_SCHEMAS = {
            'content_vectors': (['rowid', 'embedding', 'content_id'], 'content_id')
        }

        # Special handling for tables with non-standard primary keys
        CUSTOM_PRIMARY_KEYS = {
            'content_chunks': 'rowid'  # content_chunks uses rowid as primary key
        }

        # Get column names for this table
        if table_name in VIRTUAL_TABLE_SCHEMAS:
            # Use hard-coded schema for virtual tables (PRAGMA table_info returns empty for vec0)
            columns, pk_column = VIRTUAL_TABLE_SCHEMAS[table_name]
            print(f"  Using hard-coded schema for virtual table '{table_name}': {columns}")
        else:
            # Use PRAGMA for regular tables
            columns = [row[1] for row in self.memory_conn.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()]
            # Use custom PK if specified, otherwise default to 'id'
            pk_column = CUSTOM_PRIMARY_KEYS.get(table_name, 'id')

        # Validate we got columns
        if not columns:
            print(f"  ❌ WARNING: No columns found for table '{table_name}', skipping sync")
            return

        column_names = ','.join(columns)
        placeholders = ','.join(['?' for _ in columns])

        # Batch inserts/updates
        inserts = []
        deletes = []

        for record_id, operation in changes:
            if operation in ('INSERT', 'UPDATE'):
                # Fetch record from memory using the correct primary key column
                row = self.memory_conn.execute(
                    f"SELECT * FROM {table_name} WHERE {pk_column} = ?",
                    (record_id,)
                ).fetchone()

                if row:
                    inserts.append(row)

            elif operation == 'DELETE':
                deletes.append(record_id)

        # Execute batch INSERT OR REPLACE
        if inserts:
            disk_conn.executemany(
                f"INSERT OR REPLACE INTO {table_name} ({column_names}) VALUES ({placeholders})",
                inserts
            )

        # Execute batch DELETE
        if deletes:
            disk_conn.executemany(
                f"DELETE FROM {table_name} WHERE {pk_column} = ?",
                [(del_id,) for del_id in deletes]
            )

    def get_metrics(self) -> dict:
        """Return current sync metrics"""
        return self.metrics.copy()

import sqlite3
import asyncio
import time
from typing import Optional
from pathlib import Path


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

        self.memory_conn.commit()
        print("✅ Sync tracking triggers created")

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
                # Open disk connection
                disk_conn = sqlite3.connect(self.disk_path)
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
        # Get column names for this table
        columns = [row[1] for row in self.memory_conn.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()]

        column_names = ','.join(columns)
        placeholders = ','.join(['?' for _ in columns])

        # Batch inserts/updates
        inserts = []
        deletes = []

        for record_id, operation in changes:
            if operation in ('INSERT', 'UPDATE'):
                # Fetch record from memory
                row = self.memory_conn.execute(
                    f"SELECT * FROM {table_name} WHERE id = ?",
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
                f"DELETE FROM {table_name} WHERE id = ?",
                [(del_id,) for del_id in deletes]
            )

    def get_metrics(self) -> dict:
        """Return current sync metrics"""
        return self.metrics.copy()

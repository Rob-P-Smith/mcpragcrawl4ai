"""
Migration 001: Add Knowledge Graph Support

Adds tables and columns for Knowledge Graph integration with kg-service.
Handles graceful degradation when KG service is unavailable.
"""

import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def column_exists(cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def upgrade(db: sqlite3.Connection) -> bool:
    """
    Add KG support to existing database

    Returns:
        True if migration successful, False otherwise
    """
    cursor = db.cursor()

    try:
        logger.info("Starting migration 001: Add KG support")

        # ====================================================================
        # 1. Add columns to crawled_content table
        # ====================================================================

        logger.info("Adding KG tracking columns to crawled_content...")

        columns_to_add = [
            ("kg_processed", "BOOLEAN DEFAULT 0"),
            ("kg_entity_count", "INTEGER DEFAULT 0"),
            ("kg_relationship_count", "INTEGER DEFAULT 0"),
            ("kg_document_id", "TEXT"),
            ("kg_processed_at", "DATETIME")
        ]

        for column, definition in columns_to_add:
            if not column_exists(cursor, "crawled_content", column):
                cursor.execute(f"ALTER TABLE crawled_content ADD COLUMN {column} {definition}")
                logger.info(f"  ✓ Added column: {column}")
            else:
                logger.info(f"  - Column already exists: {column}")

        # Create index on kg_processed
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_crawled_content_kg
            ON crawled_content(kg_processed, kg_processed_at)
        """)

        # ====================================================================
        # 2. Read and execute SQL migration file
        # ====================================================================

        logger.info("Creating KG tables from SQL file...")

        # Read SQL file
        import os
        sql_file_path = os.path.join(
            os.path.dirname(__file__),
            "001_add_kg_support.sql"
        )

        if os.path.exists(sql_file_path):
            with open(sql_file_path, 'r') as f:
                sql_script = f.read()

            # Execute SQL script (tables with IF NOT EXISTS)
            cursor.executescript(sql_script)
            logger.info("  ✓ KG tables created")
        else:
            logger.warning(f"  ! SQL file not found: {sql_file_path}")
            # Fallback: create tables inline
            _create_tables_inline(cursor)

        # ====================================================================
        # 3. Commit changes
        # ====================================================================

        db.commit()
        logger.info("✓ Migration 001 complete")

        # Log summary
        _log_migration_summary(cursor)

        return True

    except Exception as e:
        logger.error(f"✗ Migration 001 failed: {e}")
        db.rollback()
        return False


def _create_tables_inline(cursor: sqlite3.Cursor):
    """Fallback: Create tables inline if SQL file not found"""

    logger.info("Creating tables inline (fallback)...")

    # content_chunks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_chunks (
            rowid INTEGER PRIMARY KEY,
            content_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            word_count INTEGER,
            kg_processed BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES crawled_content(id) ON DELETE CASCADE
        )
    """)

    # chunk_entities
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunk_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_rowid INTEGER NOT NULL,
            content_id INTEGER NOT NULL,
            entity_text TEXT NOT NULL,
            entity_normalized TEXT,
            entity_type_primary TEXT,
            entity_type_sub1 TEXT,
            entity_type_sub2 TEXT,
            entity_type_sub3 TEXT,
            confidence REAL,
            offset_start INTEGER,
            offset_end INTEGER,
            neo4j_node_id TEXT,
            spans_multiple_chunks BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chunk_rowid) REFERENCES content_chunks(rowid) ON DELETE CASCADE,
            FOREIGN KEY (content_id) REFERENCES crawled_content(id) ON DELETE CASCADE
        )
    """)

    # chunk_relationships
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunk_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            subject_entity TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object_entity TEXT NOT NULL,
            confidence REAL,
            context TEXT,
            neo4j_relationship_id TEXT,
            spans_chunks BOOLEAN DEFAULT 0,
            chunk_rowids TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES crawled_content(id) ON DELETE CASCADE
        )
    """)

    # kg_processing_queue
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kg_processing_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 1,
            queued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processing_started_at DATETIME,
            processed_at DATETIME,
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,
            result_summary TEXT,
            skipped_reason TEXT,
            FOREIGN KEY (content_id) REFERENCES crawled_content(id) ON DELETE CASCADE
        )
    """)

    logger.info("  ✓ Tables created inline")


def _log_migration_summary(cursor: sqlite3.Cursor):
    """Log summary of migration results"""

    # Count existing data
    cursor.execute("SELECT COUNT(*) FROM crawled_content")
    content_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM content_chunks")
    chunk_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM chunk_entities")
    entity_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM kg_processing_queue")
    queue_count = cursor.fetchone()[0]

    logger.info("=" * 60)
    logger.info("Migration Summary:")
    logger.info(f"  Crawled content: {content_count} documents")
    logger.info(f"  Content chunks: {chunk_count}")
    logger.info(f"  Chunk entities: {entity_count}")
    logger.info(f"  Queue items: {queue_count}")
    logger.info("=" * 60)


def downgrade(db: sqlite3.Connection) -> bool:
    """
    Remove KG support (for rollback)

    WARNING: This will delete all KG data!

    Returns:
        True if downgrade successful, False otherwise
    """
    cursor = db.cursor()

    try:
        logger.warning("Starting migration 001 DOWNGRADE - will remove KG data!")

        # Drop KG tables
        cursor.execute("DROP TABLE IF EXISTS kg_processing_queue")
        cursor.execute("DROP TABLE IF EXISTS chunk_relationships")
        cursor.execute("DROP TABLE IF EXISTS chunk_entities")
        cursor.execute("DROP TABLE IF EXISTS content_chunks")

        # Note: Cannot easily remove columns in SQLite
        # Columns will remain but be unused
        logger.warning("  ! KG columns in crawled_content will remain (SQLite limitation)")

        db.commit()
        logger.info("✓ Migration 001 downgraded")
        return True

    except Exception as e:
        logger.error(f"✗ Downgrade failed: {e}")
        db.rollback()
        return False


def check_migration_needed(db: sqlite3.Connection) -> bool:
    """
    Check if this migration needs to run

    Returns:
        True if migration needed, False if already applied
    """
    cursor = db.cursor()

    # Check if content_chunks table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='content_chunks'
    """)

    return cursor.fetchone() is None


if __name__ == "__main__":
    # Test migration
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 2:
        print("Usage: python 001_add_kg_support.py <database_path>")
        sys.exit(1)

    db_path = sys.argv[1]

    print(f"Testing migration on: {db_path}")

    conn = sqlite3.connect(db_path)

    if check_migration_needed(conn):
        print("\nMigration needed - running upgrade...")
        success = upgrade(conn)
        if success:
            print("✓ Migration successful!")
        else:
            print("✗ Migration failed!")
            sys.exit(1)
    else:
        print("Migration already applied")

    conn.close()

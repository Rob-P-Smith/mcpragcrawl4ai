"""
Data storage and database operations for Crawl4AI RAG system
Handles all database interactions, content storage, and retrieval
"""

import sqlite3
import sqlite_vec
import os
import sys
import time
import hashlib
import uuid
import traceback
import logging
import threading
import numpy as np
import asyncio
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional
from langdetect import detect, LangDetectException

from sentence_transformers import SentenceTransformer
from core.data.sync_manager import DBSyncManager
from core.data.content_cleaner import ContentCleaner
from core.data.kg_queue import KGQueueManager, get_vector_rowids_for_content
from core.data.kg_config import get_kg_config

GLOBAL_MODEL = SentenceTransformer('all-MiniLM-L6-v2')

class RAGDatabase:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Check environment variable first
            db_path = os.getenv("DB_PATH")
            if db_path is None:
                # Fallback to defaults
                if os.path.exists("/app/data"):
                    db_path = "/app/data/crawl4ai_rag.db"
                else:
                    db_path = "crawl4ai_rag.db"
        self.db_path = db_path
        self.db = None
        self.session_id = str(uuid.uuid4())
        self.embedder = GLOBAL_MODEL
        self.db_lock = threading.RLock()
        self._connection_closed = False

        # RAM Database support
        self.is_memory_mode = os.getenv("USE_MEMORY_DB", "true").lower() == "true"
        self.sync_manager = None

        if self.is_memory_mode:
            print("🚀 RAM Database mode enabled")
            self.sync_manager = DBSyncManager(db_path)
            # Connection will be set by initialize_async()
            # Don't call init_database() yet
        else:
            print("💾 Disk Database mode (traditional)")
            self.init_database()

    async def initialize_async(self):
        """
        Initialize memory database (called from start_api_server.py on startup)
        Only needed when USE_MEMORY_DB=true
        """
        if self.sync_manager and self.db is None:
            # First, ensure disk DB has tables (create if needed)
            temp_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.load_sqlite_vec(temp_conn)
            # Create tables in disk DB if they don't exist
            temp_conn.executescript('''
                CREATE TABLE IF NOT EXISTS crawled_content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    content TEXT,
                    markdown TEXT,
                    content_hash TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    added_by_session TEXT,
                    retention_policy TEXT DEFAULT 'permanent',
                    tags TEXT,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_active DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS blocked_domains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            temp_conn.commit()
            temp_conn.close()

            # Now load into memory with sync manager
            self.db = await self.sync_manager.initialize()
            # Complete initialization (vectors, session, blocked domains)
            self.init_database()
            print("✅ RAM Database initialized and ready")
        elif not self.is_memory_mode and self.db is None:
            # Fallback for disk mode
            self.init_database()

    def __del__(self):
        self.close()

    def close(self):
        with self.db_lock:
            if self.db is not None and not self._connection_closed:
                try:
                    self.db.close()
                    self._connection_closed = True
                except Exception as e:
                    log_error("close_database", e)

    @contextmanager
    def get_db_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.load_sqlite_vec(conn)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    @contextmanager
    def transaction(self):
        with self.db_lock:
            try:
                yield self.db
                self.db.commit()
            except Exception:
                if self.db:
                    self.db.rollback()
                raise

    def execute_with_retry(self, query: str, params=None, max_retries: int = 3):
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                with self.db_lock:
                    if params is None:
                        return self.db.execute(query)
                    else:
                        return self.db.execute(query, params)
            except sqlite3.OperationalError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    sleep_time = 0.1 * (2 ** attempt)
                    time.sleep(sleep_time)
                    log_error(f"execute_with_retry_attempt_{attempt}", e)
                continue
            except Exception as e:
                raise
        
        raise last_exception

    def load_sqlite_vec(self, db):
        package_dir = os.path.dirname(sqlite_vec.__file__)
        extension_path = os.path.join(package_dir, 'vec0.so')
        db.enable_load_extension(True)
        db.load_extension(extension_path)
        return db

    def init_database(self):
        try:
            with self.db_lock:
                # Only create new connection if not already set by sync_manager
                if self.db is None:
                    self.db = sqlite3.connect(self.db_path, check_same_thread=False)
                    self.load_sqlite_vec(self.db)

                self.db.executescript('''
                    CREATE TABLE IF NOT EXISTS crawled_content (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT UNIQUE NOT NULL,
                        title TEXT,
                        content TEXT,
                        markdown TEXT,
                        content_hash TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        added_by_session TEXT,
                        retention_policy TEXT DEFAULT 'permanent',
                        tags TEXT,
                        metadata TEXT
                    );

                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_active DATETIME DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS blocked_domains (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pattern TEXT UNIQUE NOT NULL,
                        description TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE VIRTUAL TABLE IF NOT EXISTS content_vectors USING vec0(
                        embedding FLOAT[384],
                        content_id INTEGER
                    );
                ''')

                self.db.execute("INSERT OR REPLACE INTO sessions (session_id, last_active) VALUES (?, CURRENT_TIMESTAMP)",
                               (self.session_id,))

                # Run KG migration if needed
                try:
                    from migrations.001_add_kg_support import check_migration_needed, upgrade

                    if check_migration_needed(self.db):
                        print("🔧 Running KG support migration...", file=sys.stderr, flush=True)
                        if upgrade(self.db):
                            print("✓ KG migration complete", file=sys.stderr, flush=True)
                        else:
                            print("⚠️  KG migration failed - KG features disabled", file=sys.stderr, flush=True)
                except ImportError:
                    # Migration not available, skip
                    pass
                except Exception as e:
                    print(f"⚠️  KG migration error: {e}", file=sys.stderr, flush=True)

                # Populate initial blocked domains if table is empty
                blocked_count = self.db.execute("SELECT COUNT(*) FROM blocked_domains").fetchone()[0]
                if blocked_count == 0:
                    initial_blocks = [
                        ("*.ru", "Block all Russian domains"),
                        ("*.cn", "Block all Chinese domains"),
                        ("*porn*", "Block URLs containing 'porn'"),
                        ("*sex*", "Block URLs containing 'sex'"),
                        ("*escort*", "Block URLs containing 'escort'"),
                        ("*massage*", "Block URLs containing 'massage'")
                    ]
                    self.db.executemany(
                        "INSERT OR IGNORE INTO blocked_domains (pattern, description) VALUES (?, ?)",
                        initial_blocks
                    )

                self.db.commit()
        except Exception as e:
            log_error("init_database", e)
            raise

    def chunk_content(self, content: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        words = content.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    def store_content(self, url: str, title: str, content: str, markdown: str,
                     retention_policy: str = 'permanent', tags: str = '',
                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            import json

            # Clean content FIRST before storing
            cleaned_result = ContentCleaner.clean_and_validate(content, markdown, url)
            cleaned_content = cleaned_result["cleaned_content"]

            # Warn if content is mostly navigation
            if cleaned_result.get("quality_warning"):
                print(f"⚠️  {cleaned_result['quality_warning']}: {url}", file=sys.stderr, flush=True)
                print(f"   Reduced from {cleaned_result['original_lines']} to {cleaned_result['cleaned_lines']} lines",
                      file=sys.stderr, flush=True)

            # Detect language - skip if not English
            try:
                detected_lang = detect(cleaned_content[:1000])  # Use first 1000 chars for detection
                if detected_lang != 'en':
                    print(f"⊘ Skipping non-English content ({detected_lang}): {url}", file=sys.stderr, flush=True)
                    return {
                        "success": False,
                        "error": f"Non-English content detected: {detected_lang}",
                        "url": url,
                        "skipped": True
                    }
            except LangDetectException:
                # If language detection fails, log warning but continue
                print(f"⚠️  Language detection failed for: {url}", file=sys.stderr, flush=True)

            # Add cleaning statistics to metadata
            if metadata is None:
                metadata = {}

            metadata.update({
                "original_size_bytes": len(markdown) if markdown else len(content),
                "cleaned_size_bytes": len(cleaned_content),
                "reduction_ratio": cleaned_result["reduction_ratio"],
                "navigation_indicators": cleaned_result["navigation_indicators"],
                "language": detected_lang if 'detected_lang' in locals() else 'unknown',
                "cleaned_at": datetime.now().isoformat()
            })

            # Hash the cleaned content (not original)
            content_hash = hashlib.sha256(cleaned_content.encode()).hexdigest()
            metadata_json = json.dumps(metadata)

            with self.transaction():
                existing = self.execute_with_retry(
                    'SELECT id FROM crawled_content WHERE url = ?', (url,)
                ).fetchone()

                if existing:
                    old_content_id = existing[0]
                    self.execute_with_retry(
                        'DELETE FROM content_vectors WHERE content_id = ?', (old_content_id,)
                    )
                    print(f"Replacing existing content for URL: {url}", file=sys.stderr, flush=True)

                # Store CLEANED content in both content and markdown fields
                cursor = self.execute_with_retry('''
                    INSERT OR REPLACE INTO crawled_content
                    (url, title, content, markdown, content_hash, added_by_session, retention_policy, tags, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (url, title, cleaned_content, cleaned_content, content_hash, self.session_id, retention_policy, tags, metadata_json))

                content_id = cursor.lastrowid

                # Generate embeddings from the same cleaned content
                self.generate_embeddings(content_id, cleaned_content)

                # NEW: Queue for KG processing (async, non-blocking)
                try:
                    kg_config = get_kg_config()
                    if kg_config.enabled:
                        # Get markdown for KG processing (full document)
                        cursor_check = self.execute_with_retry(
                            'SELECT markdown, title FROM crawled_content WHERE id = ?',
                            (content_id,)
                        )
                        row = cursor_check.fetchone()
                        if row:
                            full_markdown = row[0]
                            doc_title = row[1]

                            # Schedule KG queue check (async)
                            try:
                                loop = asyncio.get_event_loop()
                                loop.create_task(
                                    self._queue_for_kg_async(content_id, url, doc_title, full_markdown)
                                )
                            except RuntimeError:
                                # Event loop not running, skip KG queuing
                                pass

                except Exception as e:
                    # Don't fail content storage if KG queuing fails
                    print(f"⚠️  KG queuing failed: {e}", file=sys.stderr, flush=True)

                # Track write for sync (non-blocking)
                # Note: content_vectors tracked separately in generate_embeddings()
                if self.sync_manager:
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(self.sync_manager.track_write('crawled_content'))
                    except RuntimeError:
                        # Event loop not running, skip tracking
                        pass

                return {
                    "success": True,
                    "content_id": content_id,
                    "url": url
                }
        except Exception as e:
            log_error("store_content", e, url)
            return {
                "success": False,
                "error": str(e),
                "url": url
            }

    def generate_embeddings(self, content_id: int, content: str):
        try:
            chunks = self.chunk_content(content)

            # Filter out navigation chunks before embedding
            filtered_chunks = ContentCleaner.filter_chunks(chunks)

            if len(filtered_chunks) == 0:
                print(f"⚠️  No quality chunks after filtering for content_id {content_id}", file=sys.stderr, flush=True)
                # Use original chunks if filtering removes everything
                filtered_chunks = chunks[:3] if len(chunks) > 0 else chunks

            if len(filtered_chunks) < len(chunks):
                print(f"   Filtered {len(chunks)} chunks → {len(filtered_chunks)} quality chunks", file=sys.stderr, flush=True)

            embeddings = self.embedder.encode(filtered_chunks)

            embedding_data = [
                (embedding.astype(np.float32).tobytes(), content_id)
                for embedding in embeddings
            ]

            with self.db_lock:
                self.db.executemany('''
                    INSERT INTO content_vectors (embedding, content_id)
                    VALUES (?, ?)
                ''', embedding_data)

                # NEW: Store chunk metadata for KG processing
                try:
                    vector_rowids = get_vector_rowids_for_content(self.db, content_id)

                    if vector_rowids and len(vector_rowids) == len(filtered_chunks):
                        kg_queue = KGQueueManager(self.db)

                        # Calculate chunk boundaries in original content
                        chunk_metadata = kg_queue.calculate_chunk_boundaries(content, filtered_chunks)

                        # Store chunk metadata
                        stored = kg_queue.store_chunk_metadata(
                            content_id,
                            chunk_metadata,
                            vector_rowids
                        )

                        if stored > 0:
                            print(f"   ✓ Stored {stored} chunk metadata records", file=sys.stderr, flush=True)

                except Exception as e:
                    # Don't fail embedding process if chunk tracking fails
                    print(f"⚠️  Chunk metadata tracking failed: {e}", file=sys.stderr, flush=True)

            # Track vector changes for RAM DB sync (can't use triggers on virtual tables)
            if self.sync_manager:
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.sync_manager.track_vector_change(content_id, 'INSERT'))
                except RuntimeError:
                    pass
        except Exception as e:
            log_error("generate_embeddings", e)
            raise

    def search_similar(self, query: str, limit: int = 5, tags: Optional[List[str]] = None) -> List[Dict]:
        """
        Search for similar content using vector similarity

        Args:
            query: Search query string
            limit: Maximum number of results
            tags: Optional list of tags to filter by (ANY match)

        Returns:
            List of matching documents with similarity scores
        """
        try:
            query_embedding = self.embedder.encode([query])[0]
            query_bytes = query_embedding.astype(np.float32).tobytes()

            # Build tag filter condition if tags provided
            if tags and len(tags) > 0:
                # Create OR conditions for tag matching
                tag_conditions = ' OR '.join(['cc.tags LIKE ?' for _ in tags])
                tag_params = [f'%{tag}%' for tag in tags]

                sql = f'''
                    SELECT
                        cc.url, cc.title, cc.markdown, cc.content, cc.timestamp, cc.tags,
                        distance
                    FROM content_vectors
                    JOIN crawled_content cc ON content_vectors.content_id = cc.id
                    WHERE embedding MATCH ? AND k = ? AND ({tag_conditions})
                    ORDER BY distance
                '''
                params = (query_bytes, limit * 5, *tag_params)  # Request more results to account for deduplication
                results = self.execute_with_retry(sql, params).fetchall()
            else:
                # No tag filtering - request more to account for deduplication
                results = self.execute_with_retry('''
                    SELECT
                        cc.url, cc.title, cc.markdown, cc.content, cc.timestamp, cc.tags,
                        distance
                    FROM content_vectors
                    JOIN crawled_content cc ON content_vectors.content_id = cc.id
                    WHERE embedding MATCH ? AND k = ?
                    ORDER BY distance
                ''', (query_bytes, limit * 5)).fetchall()

            # Deduplicate by URL - keep only the best match per URL
            seen_urls = {}
            for row in results:
                url = row[0]
                distance = row[6]
                # Content is already cleaned during storage - use as-is
                content_text = row[2] if row[2] else row[3]

                if url not in seen_urls or distance < seen_urls[url]['distance']:
                    seen_urls[url] = {
                        'url': row[0],
                        'title': row[1],
                        'content': content_text[:10000] + '...' if len(content_text) > 10000 else content_text,
                        'timestamp': row[4],
                        'tags': row[5],
                        'distance': distance,
                        'similarity_score': 1 - distance if distance <= 1.0 else 1.0 / (1.0 + distance)
                    }

            # Sort by similarity and limit
            deduplicated = sorted(seen_urls.values(), key=lambda x: x['similarity_score'], reverse=True)[:limit]

            # Remove distance field from output
            return [
                {k: v for k, v in result.items() if k != 'distance'}
                for result in deduplicated
            ]
        except Exception as e:
            log_error("search_similar", e)
            raise

    async def _queue_for_kg_async(
        self,
        content_id: int,
        url: str,
        title: str,
        markdown: str
    ):
        """
        Queue content for KG processing (async helper method)

        This method checks KG service health and queues the content if available.
        Falls back gracefully if service is unavailable.
        """
        try:
            kg_queue = KGQueueManager(self.db)

            # Check health and queue (async)
            queued = await kg_queue.queue_for_kg_processing(content_id, priority=1)

            if queued:
                logger.info(f"✓ Queued content_id={content_id} for KG processing")
            else:
                # Marked as skipped or service unavailable
                logger.debug(f"Skipped KG queuing for content_id={content_id}")

        except Exception as e:
            logger.error(f"Error in KG queuing async: {e}")
            # Don't propagate - KG is optional

    def target_search(self, query: str, initial_limit: int = 5, expanded_limit: int = 20) -> Dict[str, Any]:
        """
        Intelligent search that discovers tags from initial results and expands search

        Args:
            query: Search query string
            initial_limit: Number of results in initial search (for tag discovery)
            expanded_limit: Maximum results in expanded tag-based search

        Returns:
            Dictionary with results, discovered tags, and expansion metadata
        """
        try:
            # Step 1: Initial semantic search to discover tags
            initial_results = self.search_similar(query, limit=initial_limit)

            # Step 2: Extract unique tags from initial results
            all_tags = set()
            for result in initial_results:
                if result.get('tags'):
                    # Split comma-separated tags and clean whitespace
                    tags = [tag.strip() for tag in result['tags'].split(',') if tag.strip()]
                    all_tags.update(tags)

            # Step 3: If no tags found, return initial results
            if not all_tags:
                return {
                    "success": True,
                    "query": query,
                    "results": initial_results,
                    "discovered_tags": [],
                    "expansion_used": False,
                    "initial_results_count": len(initial_results),
                    "expanded_results_count": len(initial_results)
                }

            # Step 4: Re-search with tag filtering for expansion
            expanded_results = self.search_similar(query, limit=expanded_limit, tags=list(all_tags))

            # Step 5: Deduplicate by URL (keep highest similarity score)
            deduped = {}
            for result in expanded_results:
                url = result['url']
                if url not in deduped or result['similarity_score'] > deduped[url]['similarity_score']:
                    deduped[url] = result

            # Step 6: Sort by similarity score (descending)
            final_results = sorted(deduped.values(), key=lambda x: x['similarity_score'], reverse=True)

            # Step 7: Return aggregated results with metadata
            return {
                "success": True,
                "query": query,
                "results": final_results,
                "discovered_tags": sorted(list(all_tags)),
                "expansion_used": True,
                "initial_results_count": len(initial_results),
                "expanded_results_count": len(final_results)
            }

        except Exception as e:
            log_error("target_search", e)
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results": [],
                "discovered_tags": [],
                "expansion_used": False
            }

    def list_content(self, retention_policy: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """
        List stored content with optional filtering and limit

        Args:
            retention_policy: Filter by retention policy
            limit: Maximum number of results to return (default 100, max 1000)

        Returns:
            Dictionary with content list, count, and metadata
        """
        # Enforce reasonable limits
        limit = min(max(1, limit), 1000)

        # Get total count
        if retention_policy:
            total_count = self.execute_with_retry('''
                SELECT COUNT(*) FROM crawled_content
                WHERE retention_policy = ?
            ''', (retention_policy,)).fetchone()[0]

            results = self.execute_with_retry('''
                SELECT url, title, timestamp, retention_policy, tags
                FROM crawled_content
                WHERE retention_policy = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (retention_policy, limit)).fetchall()
        else:
            total_count = self.execute_with_retry('''
                SELECT COUNT(*) FROM crawled_content
            ''').fetchone()[0]

            results = self.execute_with_retry('''
                SELECT url, title, timestamp, retention_policy, tags
                FROM crawled_content
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,)).fetchall()

        content_list = [
            {
                'url': row[0],
                'title': row[1],
                'timestamp': row[2],
                'retention_policy': row[3],
                'tags': row[4]
            }
            for row in results
        ]

        return {
            'content': content_list,
            'count': len(content_list),
            'total_count': total_count,
            'limited': total_count > limit,
            'limit': limit
        }

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

    def _get_stats_from_ram_db(self) -> Dict[str, Any]:
        """Get stats by querying the in-memory database directly"""
        try:
            # Basic counts
            pages = self.db.execute('SELECT COUNT(*) FROM crawled_content').fetchone()[0]

            # Try to get embeddings count (requires sqlite-vec)
            vec_available = False
            try:
                import sqlite_vec
                # Check if extension is already loaded by trying a query
                try:
                    embeddings = self.db.execute('SELECT COUNT(*) FROM content_vectors').fetchone()[0]
                    vec_available = True
                except:
                    embeddings = None
            except:
                embeddings = None

            sessions = self.db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]

            # Database size (for RAM DB, report the disk size since memory size isn't meaningful)
            if os.path.exists(self.db_path):
                size_bytes = os.path.getsize(self.db_path)
                size_mb = size_bytes / 1024 / 1024
            else:
                size_bytes = 0
                size_mb = 0

            # Retention policy breakdown
            retention_stats = self.db.execute('''
                SELECT retention_policy, COUNT(*) as count
                FROM crawled_content
                GROUP BY retention_policy
                ORDER BY count DESC
            ''').fetchall()

            retention_breakdown = {policy: count for policy, count in retention_stats}

            # Recent activity (last 10 pages)
            recent = self.db.execute('''
                SELECT url, title, timestamp,
                       LENGTH(content) as content_size,
                       retention_policy
                FROM crawled_content
                ORDER BY timestamp DESC
                LIMIT 10
            ''').fetchall()

            recent_activity = []
            for url, title, timestamp, size, policy in recent:
                recent_activity.append({
                    "url": url,
                    "title": title or "No title",
                    "timestamp": timestamp,
                    "size_kb": round(size / 1024, 1) if size else 0,
                    "retention_policy": policy
                })

            # Storage breakdown
            content_size = self.db.execute('''
                SELECT SUM(LENGTH(content) + LENGTH(COALESCE(markdown, '')) + LENGTH(COALESCE(title, '')))
                FROM crawled_content
            ''').fetchone()[0] or 0

            if isinstance(embeddings, int):
                embedding_size = embeddings * 384 * 4  # 384-dim float32
            else:
                embedding_size = 0

            content_mb = content_size / 1024 / 1024
            embedding_mb = embedding_size / 1024 / 1024
            metadata_mb = max(0, size_mb - content_mb - embedding_mb)

            # Top tags
            tags_result = self.db.execute('''
                SELECT tags, COUNT(*) as count
                FROM crawled_content
                WHERE tags IS NOT NULL AND tags != ''
                GROUP BY tags
                ORDER BY count DESC
                LIMIT 5
            ''').fetchall()

            top_tags = [{"tag": tag, "count": count} for tag, count in tags_result]

            # Add sync metrics if available
            sync_metrics = {}
            if self.sync_manager:
                sync_metrics = self.sync_manager.get_metrics()

            return {
                "success": True,
                "using_ram_db": True,
                "database_path": os.path.abspath(self.db_path),
                "total_pages": pages,
                "vector_embeddings": embeddings,
                "sessions": sessions,
                "database_size_mb": round(size_mb, 2),
                "database_size_bytes": size_bytes,
                "retention_breakdown": retention_breakdown,
                "recent_activity": recent_activity,
                "storage_breakdown": {
                    "content_mb": round(content_mb, 2),
                    "embeddings_mb": round(embedding_mb, 2),
                    "metadata_mb": round(metadata_mb, 2)
                },
                "top_tags": top_tags,
                "vec_extension_available": vec_available,
                "sync_metrics": sync_metrics
            }

        except Exception as e:
            return {
                "success": False,
                "using_ram_db": True,
                "error": f"Error reading RAM database: {str(e)}"
            }

    def list_domains(self) -> Dict[str, Any]:
        """
        List all unique domains from stored URLs with page counts

        Returns:
            Dictionary with domains array, total domains, and total pages
        """
        try:
            from urllib.parse import urlparse

            # Get all URLs from database
            results = self.execute_with_retry('''
                SELECT url FROM crawled_content
            ''').fetchall()

            # Extract and count domains
            domain_counts = {}
            for row in results:
                url = row[0]
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc or parsed.path
                    # Remove 'www.' prefix if present
                    if domain.startswith('www.'):
                        domain = domain[4:]

                    if domain:
                        domain_counts[domain] = domain_counts.get(domain, 0) + 1
                except Exception:
                    # Skip invalid URLs
                    continue

            # Sort by page count (descending)
            sorted_domains = [
                {"domain": domain, "page_count": count}
                for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
            ]

            return {
                "success": True,
                "domains": sorted_domains,
                "total_domains": len(sorted_domains),
                "total_pages": sum(d["page_count"] for d in sorted_domains)
            }

        except Exception as e:
            log_error("list_domains", e)
            return {
                "success": False,
                "error": str(e),
                "domains": [],
                "total_domains": 0,
                "total_pages": 0
            }

    def is_domain_blocked(self, url: str) -> Dict[str, Any]:
        """
        Check if a URL matches any blocked domain patterns.
        Supports wildcard patterns (*.ru) and keyword matching (*porn*)
        """
        try:
            from urllib.parse import urlparse

            # Parse the URL to get the domain
            parsed = urlparse(url.lower())
            domain = parsed.netloc or parsed.path
            full_url = url.lower()

            # Get all blocked patterns
            patterns = self.execute_with_retry('SELECT pattern, description FROM blocked_domains').fetchall()

            for pattern, description in patterns:
                pattern_lower = pattern.lower()

                # Handle wildcard at start: *.ru matches anything ending with .ru
                if pattern_lower.startswith('*.'):
                    suffix = pattern_lower[1:]  # Remove the *
                    if domain.endswith(suffix):
                        return {
                            "blocked": True,
                            "pattern": pattern,
                            "reason": description or f"Matches pattern: {pattern}",
                            "url": url
                        }

                # Handle wildcards on both sides: *porn* matches anywhere in URL
                elif pattern_lower.startswith('*') and pattern_lower.endswith('*'):
                    keyword = pattern_lower[1:-1]  # Remove both *
                    if keyword in full_url or keyword in domain:
                        return {
                            "blocked": True,
                            "pattern": pattern,
                            "reason": description or f"Matches pattern: {pattern}",
                            "url": url
                        }

                # Exact domain match
                elif pattern_lower == domain:
                    return {
                        "blocked": True,
                        "pattern": pattern,
                        "reason": description or f"Matches pattern: {pattern}",
                        "url": url
                    }

            return {"blocked": False, "url": url}

        except Exception as e:
            log_error("is_domain_blocked", e, url)
            # In case of error, allow the URL (fail open)
            return {"blocked": False, "url": url, "error": str(e)}

    def add_blocked_domain(self, pattern: str, description: str = "") -> Dict[str, Any]:
        """Add a domain pattern to the blocklist"""
        try:
            with self.transaction():
                self.execute_with_retry(
                    'INSERT INTO blocked_domains (pattern, description) VALUES (?, ?)',
                    (pattern, description)
                )

            return {
                "success": True,
                "pattern": pattern,
                "description": description
            }
        except sqlite3.IntegrityError:
            return {
                "success": False,
                "error": f"Pattern '{pattern}' already exists in blocklist"
            }
        except Exception as e:
            log_error("add_blocked_domain", e)
            return {
                "success": False,
                "error": str(e)
            }

    def remove_blocked_domain(self, pattern: str, keyword: str = "") -> Dict[str, Any]:
        """Remove a domain pattern from the blocklist (requires authorization keyword)"""
        try:
            # Authorization check using environment variable
            import os
            REQUIRED_KEYWORD = os.getenv("BLOCKED_DOMAIN_KEYWORD", "")
            if not REQUIRED_KEYWORD or keyword != REQUIRED_KEYWORD:
                return {
                    "success": False,
                    "error": "Unauthorized"
                }

            with self.transaction():
                cursor = self.execute_with_retry(
                    'DELETE FROM blocked_domains WHERE pattern = ?',
                    (pattern,)
                )

                if cursor.rowcount == 0:
                    return {
                        "success": False,
                        "error": f"Pattern '{pattern}' not found in blocklist"
                    }

                return {
                    "success": True,
                    "pattern": pattern,
                    "removed": True
                }
        except Exception as e:
            log_error("remove_blocked_domain", e)
            return {
                "success": False,
                "error": str(e)
            }

    def list_blocked_domains(self) -> Dict[str, Any]:
        """List all blocked domain patterns"""
        try:
            results = self.execute_with_retry(
                'SELECT pattern, description, created_at FROM blocked_domains ORDER BY created_at DESC'
            ).fetchall()

            blocked_list = [
                {
                    "pattern": pattern,
                    "description": description,
                    "created_at": created_at
                }
                for pattern, description, created_at in results
            ]

            return {
                "success": True,
                "blocked_domains": blocked_list,
                "count": len(blocked_list)
            }
        except Exception as e:
            log_error("list_blocked_domains", e)
            return {
                "success": False,
                "error": str(e),
                "blocked_domains": [],
                "count": 0
            }

    def remove_content(self, url: str = None, session_only: bool = False) -> int:
        try:
            with self.transaction():
                if session_only:
                    cursor = self.execute_with_retry('''
                        DELETE FROM crawled_content
                        WHERE added_by_session = ? AND retention_policy = 'session_only'
                    ''', (self.session_id,))
                elif url:
                    cursor = self.execute_with_retry('DELETE FROM crawled_content WHERE url = ?', (url,))
                else:
                    return 0

                return cursor.rowcount
        except Exception as e:
            log_error("remove_content", e, url if url else "")
            raise

def setup_error_logging():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, 'crawl4ai_rag_errors.log')
    logger = logging.getLogger('crawl4ai_rag')
    logger.setLevel(logging.ERROR)    
    logger.handlers.clear()    
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

ERROR_LOGGER = setup_error_logging()

def log_error(calling_function: str, error: Exception, url: str = "", error_code: str = ""):
    timestamp = datetime.now().isoformat()
    error_message = str(error)
    stack_trace = traceback.format_exc()
    
    log_entry = f"{timestamp}|{calling_function}|{url}|{error_message}|{error_code}|{stack_trace}"
    ERROR_LOGGER.error(log_entry)
    print(f"Error logged: {calling_function} - {error_message}", file=sys.stderr, flush=True)

GLOBAL_DB = RAGDatabase()

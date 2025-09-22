"""
Data storage and database operations for Crawl4AI RAG system
Handles all database interactions, content storage, and retrieval
"""

import sqlite3
import sqlite_vec
import os
import hashlib
import uuid
import traceback
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional

from sentence_transformers import SentenceTransformer
GLOBAL_MODEL = SentenceTransformer('all-MiniLM-L6-v2')

class RAGDatabase:
    def __init__(self, db_path: str = None):
        if db_path is None:
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

                    CREATE VIRTUAL TABLE IF NOT EXISTS content_vectors USING vec0(
                        embedding FLOAT[384],
                        content_id INTEGER
                    );
                ''')

                self.db.execute("INSERT OR REPLACE INTO sessions (session_id, last_active) VALUES (?, CURRENT_TIMESTAMP)",
                               (self.session_id,))
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
                     retention_policy: str = 'permanent', tags: str = '') -> int:
        try:
            content_hash = hashlib.sha256(content.encode()).hexdigest()

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

                cursor = self.execute_with_retry('''
                    INSERT OR REPLACE INTO crawled_content
                    (url, title, content, markdown, content_hash, added_by_session, retention_policy, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (url, title, content, markdown, content_hash, self.session_id, retention_policy, tags))

                content_id = cursor.lastrowid
                self.generate_embeddings(content_id, content)
                return content_id
        except Exception as e:
            log_error("store_content", e, url)
            raise

    def generate_embeddings(self, content_id: int, content: str):
        try:
            chunks = self.chunk_content(content)
            embeddings = self.embedder.encode(chunks)

            embedding_data = [
                (embedding.astype(np.float32).tobytes(), content_id)
                for embedding in embeddings
            ]
            
            with self.db_lock:
                self.db.executemany('''
                    INSERT INTO content_vectors (embedding, content_id)
                    VALUES (?, ?)
                ''', embedding_data)
        except Exception as e:
            log_error("generate_embeddings", e)
            raise

    def search_similar(self, query: str, limit: int = 5) -> List[Dict]:
        try:
            query_embedding = self.embedder.encode([query])[0]
            query_bytes = query_embedding.astype(np.float32).tobytes()

            results = self.execute_with_retry('''
                SELECT
                    cc.url, cc.title, cc.content, cc.timestamp, cc.tags,
                    distance
                FROM content_vectors
                JOIN crawled_content cc ON content_vectors.content_id = cc.id
                WHERE embedding MATCH ? AND k = ?
                ORDER BY distance
            ''', (query_bytes, limit)).fetchall()

            return [
                {
                    'url': row[0],
                    'title': row[1],
                    'content': row[2][:500] + '...' if len(row[2]) > 500 else row[2],
                    'timestamp': row[3],
                    'tags': row[4],
                    'similarity_score': 1 - row[5] if row[5] <= 1.0 else 1.0 / (1.0 + row[5])
                }
                for row in results
            ]
        except Exception as e:
            log_error("search_similar", e)
            raise

    def list_content(self, retention_policy: Optional[str] = None) -> List[Dict]:
        if retention_policy:
            results = self.execute_with_retry('''
                SELECT url, title, timestamp, retention_policy, tags
                FROM crawled_content
                WHERE retention_policy = ?
                ORDER BY timestamp DESC
            ''', (retention_policy,)).fetchall()
        else:
            results = self.execute_with_retry('''
                SELECT url, title, timestamp, retention_policy, tags
                FROM crawled_content
                ORDER BY timestamp DESC
            ''').fetchall()

        return [
            {
                'url': row[0],
                'title': row[1],
                'timestamp': row[2],
                'retention_policy': row[3],
                'tags': row[4]
            }
            for row in results
        ]

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

#!/usr/bin/env python3
"""
Fixed Crawl4AI RAG MCP Server
Corrected vector search syntax for sqlite-vec with full error logging
"""

# Pre-load all heavy dependencies at module level
import sys
import json
import asyncio
import sqlite3
import sqlite_vec
import os
import hashlib
import uuid
import traceback
import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
import numpy as np
from urllib.parse import urlparse
import re

def validate_url(url: str) -> bool:
    """Validate URL to prevent SSRF attacks"""
    try:
        parsed = urlparse(url)
        
        # Only allow http and https protocols
        if parsed.scheme not in ['http', 'https']:
            return False
            
        # Block localhost and private IP ranges
        hostname = parsed.hostname
        if not hostname:
            return False
            
        # Block localhost variations
        if hostname.lower() in ['localhost', '127.0.0.1', '::1']:
            return False
            
        # Block private IP ranges (RFC 1918)
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            # Not an IP address, check for internal hostnames
            if any(hostname.lower().endswith(suffix) for suffix in ['.local', '.internal', '.corp']):
                return False
                
        # Block cloud metadata endpoints
        metadata_ips = ['169.254.169.254', '100.100.100.200', '192.0.0.192']
        if hostname in metadata_ips:
            return False
            
        return True
        
    except Exception:
        return False

def validate_string_length(value: str, max_length: int, field_name: str) -> str:
    """Validate and truncate string to maximum length"""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    
    if len(value) > max_length:
        log_error("input_validation", ValueError(f"{field_name} exceeds maximum length of {max_length}"))
        return value[:max_length]
    
    return value

def validate_integer_range(value: int, min_val: int, max_val: int, field_name: str) -> int:
    """Validate integer is within acceptable range"""
    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} must be an integer")
    
    if value < min_val or value > max_val:
        raise ValueError(f"{field_name} must be between {min_val} and {max_val}")
    
    return value

def setup_error_logging():
    """Setup error logging to crawl4ai_rag_errors.log"""
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
    """Log detailed error information with pipe-separated format"""
    timestamp = datetime.now().isoformat()
    error_message = str(error)
    stack_trace = traceback.format_exc()
    
    log_entry = f"{timestamp}|{calling_function}|{url}|{error_message}|{error_code}|{stack_trace}"
    ERROR_LOGGER.error(log_entry)
    print(f"Error logged: {calling_function} - {error_message}", file=sys.stderr, flush=True)

from sentence_transformers import SentenceTransformer
GLOBAL_MODEL = SentenceTransformer('all-MiniLM-L6-v2')

class RAGDatabase:
    def __init__(self, db_path: str = "crawl4ai_rag.db"):
        self.db_path = db_path
        self.db = None
        self.session_id = str(uuid.uuid4())
        self.embedder = GLOBAL_MODEL
        self.db_lock = threading.Lock()  # Thread safety
        self._connection_closed = False
        self.init_database()

    def __del__(self):
        """Destructor to ensure database connection is properly closed"""
        self.close()

    def close(self):
        """Explicitly close the database connection"""
        with self.db_lock:
            if self.db is not None and not self._connection_closed:
                try:
                    self.db.close()
                    self._connection_closed = True
                except Exception as e:
                    log_error("close_database", e)

    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections with automatic cleanup"""
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
        """Context manager for database transactions with rollback on error"""
        with self.db_lock:
            try:
                yield self.db
                self.db.commit()
            except Exception:
                if self.db:
                    self.db.rollback()
                raise

    def execute_with_retry(self, query: str, params=None, max_retries: int = 3):
        """Execute query with retry logic for transient failures"""
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
                    # Exponential backoff
                    sleep_time = 0.1 * (2 ** attempt)
                    time.sleep(sleep_time)
                    log_error(f"execute_with_retry_attempt_{attempt}", e)
                continue
            except Exception as e:
                # Non-retryable exceptions
                raise
        
        # If all retries failed, raise the last exception
        raise last_exception

    def load_sqlite_vec(self, db):
        """Helper function to load sqlite-vec extension with full path"""
        package_dir = os.path.dirname(sqlite_vec.__file__)
        extension_path = os.path.join(package_dir, 'vec0.so')
        db.enable_load_extension(True)
        db.load_extension(extension_path)
        return db

    def init_database(self):
        """Initialize SQLite database with vector capabilities"""
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

            # Use transaction to ensure content and embeddings are stored atomically
            with self.transaction():
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

            # Batch insert embeddings for better performance
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

class Crawl4AIRAG:
    def __init__(self):
        self.crawl4ai_url = "http://localhost:11235"
        self.db = RAGDatabase()

    async def crawl_url(self, url: str, return_full_content: bool = False) -> Dict[str, Any]:
        try:
            response = requests.post(
                f"{self.crawl4ai_url}/crawl",
                json={"urls": [url]},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success") and result.get("results"):
                crawl_result = result["results"][0]
                content = crawl_result.get("cleaned_html", "")
                markdown = crawl_result.get("markdown", {}).get("raw_markdown", "")
                title = crawl_result.get("metadata", {}).get("title", "")
                
                if return_full_content:
                    return {
                        "success": True,
                        "url": url,
                        "title": title,
                        "content": content,
                        "markdown": markdown
                    }
                else:
                    return {
                        "success": True,
                        "url": url,
                        "title": title,
                        "content_preview": content[:300] + "..." if len(content) > 300 else content,
                        "content_length": len(content),
                        "message": f"Crawled '{title}' - {len(content)} characters"
                    }
        except Exception as e:
            log_error("crawl_url", e, url)
            return {"success": False, "error": str(e)}

    async def crawl_and_store(self, url: str, retention_policy: str = 'permanent',
                            tags: str = '') -> Dict[str, Any]:
        try:
            crawl_result = await self.crawl_url(url, return_full_content=True)

            if not crawl_result.get("success"):
                return crawl_result

            content_id = self.db.store_content(
                url=url,
                title=crawl_result["title"],
                content=crawl_result["content"],
                markdown=crawl_result["markdown"],
                retention_policy=retention_policy,
                tags=tags
            )

            return {
                "success": True,
                "url": url,
                "title": crawl_result["title"],
                "content_preview": crawl_result["content"][:200] + "..." if len(crawl_result["content"]) > 200 else crawl_result["content"],
                "content_length": len(crawl_result["content"]),
                "stored": True,
                "content_id": content_id,
                "retention_policy": retention_policy,
                "message": f"Successfully crawled and stored '{crawl_result['title']}' ({len(crawl_result['content'])} characters)"
            }
        except Exception as e:
            log_error("crawl_and_store", e, url)
            return {"success": False, "error": str(e)}

    async def search_knowledge(self, query: str, limit: int = 5) -> Dict[str, Any]:
        try:
            results = self.db.search_similar(query, limit)
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            log_error("search_knowledge", e)
            return {"success": False, "error": str(e)}

print("Initializing RAG system...", file=sys.stderr, flush=True)
GLOBAL_RAG = Crawl4AIRAG()
print("RAG system ready!", file=sys.stderr, flush=True)

class MCPServer:
    def __init__(self):
        self.rag = GLOBAL_RAG
        self.tools = [
            {
                "name": "crawl_url",
                "description": "Crawl a URL and return content without storing it",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to crawl"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "crawl_and_remember",
                "description": "Crawl a URL and permanently store it in the knowledge base",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to crawl"},
                        "tags": {"type": "string", "description": "Optional tags for organization"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "crawl_temp",
                "description": "Crawl a URL and store temporarily (session only)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to crawl"},
                        "tags": {"type": "string", "description": "Optional tags for organization"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "search_memory",
                "description": "Search stored knowledge using semantic similarity",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Number of results (default 5)"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "list_memory",
                "description": "List all stored content in the knowledge base",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string", "description": "Filter by retention policy (permanent, session_only, 30_days)"}
                    }
                }
            },
            {
                "name": "forget_url",
                "description": "Remove specific content by URL",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to remove"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "clear_temp_memory",
                "description": "Clear all temporary content from current session",
                "inputSchema": {"type": "object", "properties": {}}
            }
        ]

    async def handle_request(self, request):
        method = request.get("method")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "crawl4ai-rag",
                        "version": "1.0.0"
                    }
                }
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {"tools": self.tools}
            }

        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            try:
                if tool_name == "crawl_url":
                    # Validate URL
                    url = arguments["url"]
                    if not validate_url(url):
                        result = {"success": False, "error": "Invalid or unsafe URL provided"}
                    else:
                        result = await self.rag.crawl_url(url)
                
                elif tool_name == "crawl_and_remember":
                    # Validate URL and tags
                    url = arguments["url"]
                    if not validate_url(url):
                        result = {"success": False, "error": "Invalid or unsafe URL provided"}
                    else:
                        tags = validate_string_length(arguments.get("tags", ""), 255, "tags")
                        result = await self.rag.crawl_and_store(
                            url,
                            retention_policy='permanent',
                            tags=tags
                        )
                
                elif tool_name == "crawl_temp":
                    # Validate URL and tags
                    url = arguments["url"]
                    if not validate_url(url):
                        result = {"success": False, "error": "Invalid or unsafe URL provided"}
                    else:
                        tags = validate_string_length(arguments.get("tags", ""), 255, "tags")
                        result = await self.rag.crawl_and_store(
                            url,
                            retention_policy='session_only',
                            tags=tags
                        )
                
                elif tool_name == "search_memory":
                    # Validate query and limit
                    query = validate_string_length(arguments["query"], 500, "query")
                    limit = validate_integer_range(arguments.get("limit", 5), 1, 1000, "limit")
                    result = await self.rag.search_knowledge(query, limit)
                
                elif tool_name == "list_memory":
                    # Validate filter parameter
                    filter_param = arguments.get("filter")
                    if filter_param:
                        filter_param = validate_string_length(filter_param, 500, "filter")
                    result = {
                        "success": True,
                        "content": self.rag.db.list_content(filter_param)
                    }
                
                elif tool_name == "forget_url":
                    # Validate URL
                    url = arguments["url"]
                    if not validate_url(url):
                        result = {"success": False, "error": "Invalid or unsafe URL provided"}
                    else:
                        removed = self.rag.db.remove_content(url=url)
                        result = {
                            "success": True,
                            "removed_count": removed,
                            "url": url
                        }
                
                elif tool_name == "clear_temp_memory":
                    removed = self.rag.db.remove_content(session_only=True)
                    result = {
                        "success": True,
                        "removed_count": removed,
                        "session_id": self.rag.db.session_id
                    }
                else:
                    result = {"success": False, "error": f"Unknown tool: {tool_name}"}

                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2)
                            }
                        ]
                    }
                }

            except ValueError as e:
                # Validation errors - return user-friendly error
                log_error(f"validation_error:{tool_name}", e, arguments.get("url", ""))
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({"success": False, "error": str(e)}, indent=2)
                            }
                        ]
                    }
                }
            except Exception as e:
                log_error(f"tools/call:{tool_name}", e, arguments.get("url", ""))
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }

        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": -32601, "message": "Method not found"}
        }

async def main():
    server = MCPServer()

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break

            request = json.loads(line.strip())
            response = await server.handle_request(request)
            print(json.dumps(response), flush=True)

        except Exception as e:
            log_error("main_loop", e)
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if 'request' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    asyncio.run(main())
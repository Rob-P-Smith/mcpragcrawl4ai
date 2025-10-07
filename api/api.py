"""
Main REST API server for Crawl4AI RAG system
Provides bidirectional communication between local MCP servers and remote deployments
"""

import os
import sys
import time
import asyncio
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv
import httpx

# Import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from operations.crawler import Crawl4AIRAG, validate_url, validate_string_length, validate_integer_range, validate_deep_crawl_params, validate_float_range
from core.data.storage import GLOBAL_DB, log_error
from core.data.dbdefense import (
    SQLInjectionDefense,
    sanitize_search_params,
    sanitize_crawl_params,
    sanitize_block_domain_params
)
from api.auth import verify_api_key, log_api_request, cleanup_sessions

# Load environment variables
load_dotenv()

# Pydantic models for request/response validation
class CrawlRequest(BaseModel):
    url: str = Field(..., description="URL to crawl")

    @validator('url')
    def validate_url_field(cls, v):
        if not validate_url(v):
            raise ValueError('Invalid or unsafe URL provided')
        return v

class CrawlStoreRequest(CrawlRequest):
    tags: Optional[str] = Field("", description="Optional tags for organization")
    retention_policy: Optional[str] = Field("permanent", description="Storage policy")

    @validator('tags')
    def validate_tags(cls, v):
        return validate_string_length(v or "", 255, "tags")

class DeepCrawlRequest(CrawlRequest):
    max_depth: Optional[int] = Field(2, ge=1, le=5, description="Maximum depth to crawl")
    max_pages: Optional[int] = Field(10, ge=1, le=250, description="Maximum pages to crawl")
    include_external: Optional[bool] = Field(False, description="Follow external domain links")
    score_threshold: Optional[float] = Field(0.0, ge=0.0, le=1.0, description="Minimum URL score")
    timeout: Optional[int] = Field(None, ge=60, le=1800, description="Timeout in seconds")

class DeepCrawlStoreRequest(DeepCrawlRequest):
    tags: Optional[str] = Field("", description="Optional tags for organization")
    retention_policy: Optional[str] = Field("permanent", description="Storage policy")

    @validator('tags')
    def validate_tags(cls, v):
        return validate_string_length(v or "", 255, "tags")

class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: Optional[int] = Field(5, ge=1, le=1000, description="Number of results")
    tags: Optional[str] = Field(None, description="Comma-separated tags to filter by (ANY match)")

    @validator('query')
    def validate_query(cls, v):
        return validate_string_length(v, 500, "query")

    @validator('tags')
    def validate_tags(cls, v):
        if v:
            return validate_string_length(v, 500, "tags")
        return v

class TargetSearchRequest(BaseModel):
    query: str = Field(..., description="Search query for intelligent tag expansion")
    initial_limit: Optional[int] = Field(5, ge=1, le=100, description="Initial results for tag discovery")
    expanded_limit: Optional[int] = Field(20, ge=1, le=1000, description="Maximum expanded results")

    @validator('query')
    def validate_query(cls, v):
        return validate_string_length(v, 500, "query")

class MemoryListRequest(BaseModel):
    filter: Optional[str] = Field(None, description="Filter by retention policy")

    @validator('filter')
    def validate_filter(cls, v):
        if v:
            return validate_string_length(v, 500, "filter")
        return v

class ForgetUrlRequest(BaseModel):
    url: str = Field(..., description="URL to remove")

    @validator('url')
    def validate_url_field(cls, v):
        if not validate_url(v):
            raise ValueError('Invalid or unsafe URL provided')
        return v

# Initialize FastAPI app
def create_app() -> FastAPI:
    app = FastAPI(
        title="Crawl4AI RAG API",
        description="REST API for Crawl4AI RAG system with bidirectional MCP communication",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS middleware
    if os.getenv("ENABLE_CORS", "true").lower() == "true":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        log_error(f"api_global_exception:{request.url.path}", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error", "timestamp": datetime.now().isoformat()}
        )

    # Initialize RAG system with Crawl4AI URL from environment
    crawl4ai_url = os.getenv("CRAWL4AI_URL", "http://localhost:11235")
    rag_system = Crawl4AIRAG(crawl4ai_url=crawl4ai_url)

    # Middleware for request logging
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        # Log the request (you can extend this)
        print(f"API {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s", flush=True)
        return response

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}

    # Help endpoint - List all available tools
    @app.get("/api/v1/help")
    async def get_help():
        help_data = {
            "success": True,
            "tools": [
                {
                    "name": "crawl_url",
                    "example": "Crawl http://www.example.com without storing",
                    "parameters": "url: string"
                },
                {
                    "name": "crawl_and_store",
                    "example": "Crawl and permanently store https://github.com/anthropics/anthropic-sdk-python",
                    "parameters": "url: string, tags?: string, retention_policy?: string"
                },
                {
                    "name": "crawl_temp",
                    "example": "Crawl and temporarily store https://news.ycombinator.com",
                    "parameters": "url: string, tags?: string"
                },
                {
                    "name": "deep_crawl_and_store",
                    "example": "Deep crawl https://docs.python.org starting from main page",
                    "parameters": "url: string, max_depth?: number (1-5, default 2), max_pages?: number (1-250, default 10), retention_policy?: string, tags?: string, include_external?: boolean, score_threshold?: number (0.0-1.0), timeout?: number (60-1800)"
                },
                {
                    "name": "search_knowledge",
                    "example": "Search for 'async python patterns' in stored knowledge",
                    "parameters": "query: string, limit?: number (default 5, max 1000), tags?: string (comma-separated tags for filtering)"
                },
                {
                    "name": "target_search",
                    "example": "Intelligent search for 'react hooks' that discovers and expands by related tags",
                    "parameters": "query: string, initial_limit?: number (1-100, default 5), expanded_limit?: number (1-1000, default 20)"
                },
                {
                    "name": "list_memory",
                    "example": "List all stored pages or filter by retention policy",
                    "parameters": "filter?: string (permanent|session_only|30_days), limit?: number (default 100, max 1000)"
                },
                {
                    "name": "get_database_stats",
                    "example": "Get database statistics including record counts and storage size",
                    "parameters": "none"
                },
                {
                    "name": "list_domains",
                    "example": "List all unique domains stored (e.g., github.com, docs.python.org)",
                    "parameters": "none"
                },
                {
                    "name": "add_blocked_domain",
                    "example": "Block all .ru domains or URLs containing 'spam'",
                    "parameters": "pattern: string (e.g., *.ru, *.cn, *spam*, example.com), description?: string"
                },
                {
                    "name": "remove_blocked_domain",
                    "example": "Unblock a previously blocked domain pattern",
                    "parameters": "pattern: string, keyword: string (authorization)"
                },
                {
                    "name": "list_blocked_domains",
                    "example": "Show all currently blocked domain patterns",
                    "parameters": "none"
                },
                {
                    "name": "forget_url",
                    "example": "Remove specific URL from knowledge base",
                    "parameters": "url: string"
                },
                {
                    "name": "clear_temp_memory",
                    "example": "Clear all temporary/session-only content",
                    "parameters": "none"
                }
            ],
            "api_info": {
                "base_url": "/api/v1",
                "authentication": "Bearer token required in Authorization header",
                "formats": {
                    "retention_policy": ["permanent", "session_only", "30_days"],
                    "http_methods": {
                        "GET": ["/status", "/memory", "/stats", "/domains", "/blocked-domains", "/help"],
                        "POST": ["/crawl", "/crawl/store", "/crawl/temp", "/crawl/deep/store", "/search", "/search/target", "/blocked-domains"],
                        "DELETE": ["/memory", "/memory/temp", "/blocked-domains"]
                    }
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        return help_data

    # API Status endpoint
    @app.get("/api/v1/status")
    async def api_status(session_info: Dict = Depends(verify_api_key)):
        try:
            # Test database connection
            db_status = "healthy"
            try:
                GLOBAL_DB.list_content()
            except Exception as e:
                db_status = f"error: {str(e)}"

            # Test crawl4ai connection
            crawl4ai_status = "healthy"
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{os.getenv('CRAWL4AI_URL', 'http://localhost:11235')}/")
                    if response.status_code != 200:
                        crawl4ai_status = "unreachable"
            except Exception as e:
                crawl4ai_status = f"error: {str(e)}"

            return {
                "success": True,
                "status": "operational",
                "components": {
                    "database": db_status,
                    "crawl4ai": crawl4ai_status,
                    "session": session_info["session_id"]
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error("api_status", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Crawl URL without storing
    @app.post("/api/v1/crawl")
    async def crawl_url(request: CrawlRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            # Sanitize URL input
            sanitized_url = SQLInjectionDefense.sanitize_url(request.url)

            result = await rag_system.crawl_url(sanitized_url)
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_crawl_url", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # Crawl and store permanently
    @app.post("/api/v1/crawl/store")
    async def crawl_and_store(request: CrawlStoreRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            # Sanitize all inputs
            sanitized = sanitize_crawl_params(
                url=request.url,
                tags=request.tags,
                retention_policy=request.retention_policy
            )

            result = await rag_system.crawl_and_store(
                sanitized['url'],
                retention_policy=sanitized.get('retention_policy', 'permanent'),
                tags=sanitized.get('tags', '')
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_crawl_store", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # Crawl and store temporarily
    @app.post("/api/v1/crawl/temp")
    async def crawl_temp(request: CrawlStoreRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            # Sanitize inputs - override retention policy for temp storage
            sanitized = sanitize_crawl_params(
                url=request.url,
                tags=request.tags,
                retention_policy="session_only"
            )

            result = await rag_system.crawl_and_store(
                sanitized['url'],
                retention_policy="session_only",
                tags=sanitized.get('tags', '')
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_crawl_temp", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # Deep crawl and store
    @app.post("/api/v1/crawl/deep/store")
    async def deep_crawl_and_store(request: DeepCrawlStoreRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            # Sanitize all inputs
            sanitized_url = SQLInjectionDefense.sanitize_url(request.url)
            sanitized_tags = SQLInjectionDefense.sanitize_tags(request.tags) if request.tags else ""
            sanitized_retention = SQLInjectionDefense.sanitize_retention_policy(request.retention_policy)

            # Sanitize integer inputs
            max_depth = SQLInjectionDefense.sanitize_integer(request.max_depth, 1, 5, "max_depth")
            max_pages = SQLInjectionDefense.sanitize_integer(request.max_pages, 1, 250, "max_pages")

            result = await rag_system.deep_crawl_and_store(
                sanitized_url,
                retention_policy=sanitized_retention,
                tags=sanitized_tags,
                max_depth=max_depth,
                max_pages=max_pages,
                include_external=request.include_external,
                score_threshold=request.score_threshold,
                timeout=request.timeout
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_deep_crawl_store", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # Search stored knowledge
    @app.post("/api/v1/search")
    async def search_memory(request: SearchRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            # Sanitize search parameters
            sanitized = sanitize_search_params(
                query=request.query,
                limit=request.limit,
                tags=request.tags
            )

            # Parse tags from sanitized comma-separated string
            tags_list = None
            if 'tags' in sanitized:
                tags_list = [tag.strip() for tag in sanitized['tags'].split(',') if tag.strip()]

            result = await rag_system.search_knowledge(
                sanitized['query'],
                sanitized['limit'],
                tags=tags_list
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_search_memory", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Target search with tag expansion
    @app.post("/api/v1/search/target")
    async def target_search(request: TargetSearchRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            # Sanitize inputs
            sanitized_query = SQLInjectionDefense.sanitize_string(
                request.query,
                max_length=1000,
                field_name="query"
            )
            initial_limit = SQLInjectionDefense.sanitize_integer(
                request.initial_limit, 1, 100, "initial_limit"
            )
            expanded_limit = SQLInjectionDefense.sanitize_integer(
                request.expanded_limit, 1, 1000, "expanded_limit"
            )

            result = await rag_system.target_search(
                sanitized_query,
                initial_limit,
                expanded_limit
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_target_search", e)
            raise HTTPException(status_code=500, detail=str(e))

    # List stored content
    @app.get("/api/v1/memory")
    async def list_memory(
        filter: Optional[str] = None,
        limit: Optional[int] = 100,
        session_info: Dict = Depends(verify_api_key)
    ):
        try:
            # Sanitize filter if provided
            if filter:
                filter = SQLInjectionDefense.sanitize_retention_policy(filter)

            # Sanitize limit
            limit = SQLInjectionDefense.sanitize_integer(
                limit or 100, min_val=1, max_val=1000, field_name="limit"
            )

            result = GLOBAL_DB.list_content(filter, limit)
            return {
                "success": True,
                "data": result,
                "timestamp": datetime.now().isoformat()
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_list_memory", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Get database statistics
    @app.get("/api/v1/stats")
    async def get_database_stats(session_info: Dict = Depends(verify_api_key)):
        try:
            stats = GLOBAL_DB.get_database_stats()
            return {
                "success": True,
                "data": stats,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error("api_get_stats", e)
            raise HTTPException(status_code=500, detail=str(e))

    # List unique domains
    @app.get("/api/v1/domains")
    async def list_domains(session_info: Dict = Depends(verify_api_key)):
        try:
            domains = GLOBAL_DB.list_domains()
            return {
                "success": True,
                "data": domains,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error("api_list_domains", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Blocked domains management
    @app.get("/api/v1/blocked-domains")
    async def list_blocked_domains(session_info: Dict = Depends(verify_api_key)):
        try:
            blocked = GLOBAL_DB.list_blocked_domains()
            return {
                "success": True,
                "data": blocked,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error("api_list_blocked_domains", e)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/blocked-domains")
    async def add_blocked_domain(request: Request, session_info: Dict = Depends(verify_api_key)):
        try:
            body = await request.json()
            pattern = body.get("pattern")
            description = body.get("description", "")

            if not pattern:
                raise HTTPException(status_code=400, detail="Pattern is required")

            # Sanitize inputs
            sanitized = sanitize_block_domain_params(
                pattern=pattern,
                description=description if description else None
            )

            result = GLOBAL_DB.add_blocked_domain(
                sanitized['pattern'],
                sanitized.get('description', '')
            )

            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("error", "Failed to add blocked domain"))

            return {
                "success": True,
                "data": result,
                "timestamp": datetime.now().isoformat()
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            log_error("api_add_blocked_domain", e)
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/v1/blocked-domains")
    async def remove_blocked_domain(pattern: str, keyword: str = "", session_info: Dict = Depends(verify_api_key)):
        try:
            if not pattern:
                raise HTTPException(status_code=400, detail="Pattern is required")

            # Sanitize inputs
            sanitized = sanitize_block_domain_params(
                pattern=pattern,
                keyword=keyword if keyword else None
            )

            # Authorization check happens in storage.py
            result = GLOBAL_DB.remove_blocked_domain(
                sanitized['pattern'],
                sanitized.get('keyword', '')
            )

            if not result.get("success"):
                if result.get("error") == "Unauthorized":
                    raise HTTPException(status_code=401, detail="Unauthorized")
                raise HTTPException(status_code=404, detail=result.get("error", "Pattern not found"))

            return {
                "success": True,
                "data": result,
                "timestamp": datetime.now().isoformat()
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            log_error("api_remove_blocked_domain", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Remove specific content
    @app.delete("/api/v1/memory")
    async def forget_url(url: str, session_info: Dict = Depends(verify_api_key)):
        try:
            # First sanitize the base URL
            sanitized_base_url = SQLInjectionDefense.sanitize_url(url)

            # Normalize URL: add https:// if missing scheme
            url_variants = []
            if not sanitized_base_url.startswith(('http://', 'https://')):
                # Try https first, then http
                url_variants.append(f"https://{sanitized_base_url}")
                url_variants.append(f"http://{sanitized_base_url}")
            else:
                url_variants.append(sanitized_base_url)

            # For each variant, try with and without www
            expanded_variants = []
            for variant in url_variants:
                expanded_variants.append(variant)
                # Add www variant
                if '://www.' not in variant:
                    expanded_variants.append(variant.replace('://', '://www.'))
                # Add non-www variant
                if '://www.' in variant:
                    expanded_variants.append(variant.replace('://www.', '://'))

            # Try to delete with each variant (all already sanitized)
            total_removed = 0
            attempted_urls = []

            for variant in expanded_variants:
                if validate_url(variant):
                    attempted_urls.append(variant)
                    removed = GLOBAL_DB.remove_content(url=variant)
                    total_removed += removed

            if not attempted_urls:
                raise HTTPException(status_code=400, detail="Invalid or unsafe URL provided")

            return {
                "success": True,
                "data": {
                    "removed_count": total_removed,
                    "attempted_urls": attempted_urls,
                    "original_url": url
                },
                "timestamp": datetime.now().isoformat()
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            log_error("api_forget_url", e, url)
            raise HTTPException(status_code=500, detail=str(e))

    # Clear temporary memory
    @app.delete("/api/v1/memory/temp")
    async def clear_temp_memory(session_info: Dict = Depends(verify_api_key)):
        try:
            removed = GLOBAL_DB.remove_content(session_only=True)
            return {
                "success": True,
                "data": {"removed_count": removed, "session_id": GLOBAL_DB.session_id},
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error("api_clear_temp_memory", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Session cleanup task
    @app.on_event("startup")
    async def startup_event():
        # Start background task for session cleanup
        asyncio.create_task(session_cleanup_task())

    async def session_cleanup_task():
        while True:
            try:
                cleanup_sessions()
                await asyncio.sleep(3600)  # Run every hour
            except Exception as e:
                log_error("session_cleanup_task", e)
                await asyncio.sleep(300)  # Retry in 5 minutes if error

    return app

# Client mode functions for MCP to API translation
class APIClient:
    def __init__(self):
        self.base_url = os.getenv("REMOTE_API_URL")
        self.api_key = os.getenv("REMOTE_API_KEY")
        self.timeout = 30.0

    async def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to remote API"""
        if not self.base_url or not self.api_key:
            raise Exception("Remote API configuration missing")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        url = f"{self.base_url.rstrip('/')}{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if method.upper() in ["GET", "DELETE"]:
                # GET and DELETE use query parameters
                response = await client.request(method, url, headers=headers, params=data)
            else:
                # POST, PUT, PATCH use JSON body
                response = await client.request(method, url, headers=headers, json=data)

            response.raise_for_status()
            return response.json()

    async def crawl_url(self, url: str) -> Dict[str, Any]:
        return await self.make_request("POST", "/api/v1/crawl", {"url": url})

    async def crawl_and_store(self, url: str, tags: str = "", retention_policy: str = "permanent") -> Dict[str, Any]:
        return await self.make_request("POST", "/api/v1/crawl/store", {
            "url": url, "tags": tags, "retention_policy": retention_policy
        })

    async def crawl_temp(self, url: str, tags: str = "") -> Dict[str, Any]:
        return await self.make_request("POST", "/api/v1/crawl/temp", {
            "url": url, "tags": tags
        })

    async def deep_crawl_dfs(self, url: str, max_depth: int = 2, max_pages: int = 10,
                            include_external: bool = False, score_threshold: float = 0.0,
                            timeout: Optional[int] = None) -> Dict[str, Any]:
        return await self.make_request("POST", "/api/v1/crawl/deep", {
            "url": url, "max_depth": max_depth, "max_pages": max_pages,
            "include_external": include_external, "score_threshold": score_threshold,
            "timeout": timeout
        })

    async def deep_crawl_and_store(self, url: str, retention_policy: str = "permanent",
                                  tags: str = "", max_depth: int = 2, max_pages: int = 10,
                                  include_external: bool = False, score_threshold: float = 0.0,
                                  timeout: Optional[int] = None) -> Dict[str, Any]:
        return await self.make_request("POST", "/api/v1/crawl/deep/store", {
            "url": url, "retention_policy": retention_policy, "tags": tags,
            "max_depth": max_depth, "max_pages": max_pages,
            "include_external": include_external, "score_threshold": score_threshold,
            "timeout": timeout
        })

    async def search_knowledge(self, query: str, limit: int = 5, tags: Optional[str] = None) -> Dict[str, Any]:
        payload = {"query": query, "limit": limit}
        if tags:
            payload["tags"] = tags
        return await self.make_request("POST", "/api/v1/search", payload)

    async def target_search(self, query: str, initial_limit: int = 5, expanded_limit: int = 20) -> Dict[str, Any]:
        return await self.make_request("POST", "/api/v1/search/target", {
            "query": query,
            "initial_limit": initial_limit,
            "expanded_limit": expanded_limit
        })

    async def list_memory(self, filter: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        params = {}
        if filter:
            params["filter"] = filter
        if limit:
            params["limit"] = limit
        return await self.make_request("GET", "/api/v1/memory", params if params else None)

    async def get_database_stats(self) -> Dict[str, Any]:
        return await self.make_request("GET", "/api/v1/stats")

    async def list_domains(self) -> Dict[str, Any]:
        return await self.make_request("GET", "/api/v1/domains")

    async def add_blocked_domain(self, pattern: str, description: str = "") -> Dict[str, Any]:
        return await self.make_request("POST", "/api/v1/blocked-domains", {
            "pattern": pattern,
            "description": description
        })

    async def remove_blocked_domain(self, pattern: str, keyword: str = "") -> Dict[str, Any]:
        return await self.make_request("DELETE", "/api/v1/blocked-domains", {"pattern": pattern, "keyword": keyword})

    async def list_blocked_domains(self) -> Dict[str, Any]:
        return await self.make_request("GET", "/api/v1/blocked-domains")

    async def forget_url(self, url: str) -> Dict[str, Any]:
        return await self.make_request("DELETE", "/api/v1/memory", {"url": url})

    async def clear_temp_memory(self) -> Dict[str, Any]:
        return await self.make_request("DELETE", "/api/v1/memory/temp")

    async def get_help(self) -> Dict[str, Any]:
        return await self.make_request("GET", "/api/v1/help")

# Initialize global API client for client mode
api_client = APIClient()

if __name__ == "__main__":
    import uvicorn

    app = create_app()

    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8080"))

    print(f"Starting Crawl4AI RAG API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
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

class KGSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: Optional[int] = Field(10, ge=1, le=1000, description="Number of results")
    tags: Optional[str] = Field(None, description="Comma-separated tags to filter by")
    enable_expansion: Optional[bool] = Field(True, description="Enable KG entity expansion")
    include_context: Optional[bool] = Field(True, description="Include context snippets")

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

    # Startup event - initialize RAM DB
    @app.on_event("startup")
    async def startup_event():
        """Initialize RAM database on startup if enabled"""
        print("🚀 Starting Crawl4AI RAG Server...")
        await GLOBAL_DB.initialize_async()
        print("✅ Server ready")

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

    # Track running deep crawl tasks
    deep_crawl_tasks = {}  # task_id -> {task, status, result, started_at}

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
        """
        Comprehensive health check for mcpragcrawl4ai and kg-project containers
        Checks container reachability, service health, and database availability
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {}
        }

        overall_healthy = True

        # Check mcpragcrawl4ai container (Crawl4AI service)
        crawl4ai_health = {
            "name": "mcpragcrawl4ai",
            "status": "unknown",
            "reachable": False,
            "database": "unknown"
        }

        try:
            crawl4ai_url = os.getenv("CRAWL4AI_URL", "http://localhost:11235")
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{crawl4ai_url}/")
                if response.status_code == 200:
                    crawl4ai_health["status"] = "healthy"
                    crawl4ai_health["reachable"] = True
                else:
                    crawl4ai_health["status"] = f"unhealthy (HTTP {response.status_code})"
                    overall_healthy = False
        except Exception as e:
            crawl4ai_health["status"] = "unhealthy"
            crawl4ai_health["error"] = str(e)
            overall_healthy = False

        # Check local database (SQLite for mcpragcrawl4ai)
        try:
            GLOBAL_DB.list_content(limit=1)
            crawl4ai_health["database"] = "healthy"
        except Exception as e:
            crawl4ai_health["database"] = f"unhealthy: {str(e)}"
            overall_healthy = False

        health_status["services"]["mcpragcrawl4ai"] = crawl4ai_health

        # Check kg-project container (Knowledge Graph service)
        kg_health = {
            "name": "kg-project",
            "status": "unknown",
            "reachable": False,
            "database": "unknown"
        }

        try:
            kg_service_url = os.getenv("KG_SERVICE_URL", "http://localhost:8088")
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check KG service health endpoint
                response = await client.get(f"{kg_service_url}/health")
                if response.status_code == 200:
                    kg_health["status"] = "healthy"
                    kg_health["reachable"] = True

                    # Try to get database status from response
                    try:
                        health_data = response.json()
                        if "database" in health_data:
                            kg_health["database"] = health_data["database"]
                        elif "neo4j" in health_data:
                            kg_health["database"] = health_data["neo4j"]
                    except:
                        pass
                else:
                    kg_health["status"] = f"unhealthy (HTTP {response.status_code})"
                    overall_healthy = False
        except Exception as e:
            kg_health["status"] = "unhealthy"
            kg_health["error"] = str(e)
            overall_healthy = False

        # If database status not retrieved from health endpoint, try direct Neo4j check
        if kg_health["database"] == "unknown" and kg_health["reachable"]:
            try:
                neo4j_url = os.getenv("NEO4J_URI", "bolt://localhost:7687")
                async with httpx.AsyncClient(timeout=3.0) as client:
                    # Try to check if Neo4j is responding (HTTP endpoint on 7474)
                    neo4j_http_url = neo4j_url.replace("bolt://", "http://").replace(":7687", ":7474")
                    response = await client.get(neo4j_http_url)
                    if response.status_code in [200, 401]:  # 401 means it's responding but needs auth
                        kg_health["database"] = "healthy"
                    else:
                        kg_health["database"] = f"unhealthy (HTTP {response.status_code})"
                        overall_healthy = False
            except Exception as e:
                kg_health["database"] = f"unhealthy: {str(e)}"
                overall_healthy = False

        health_status["services"]["kg-project"] = kg_health

        # Update overall status
        if not overall_healthy:
            health_status["status"] = "degraded"

        return health_status

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
                    "name": "simple_search",
                    "example": "Simple vector similarity search for 'FastAPI authentication' without KG enhancement",
                    "parameters": "query: string, limit?: number (default 10, max 1000), tags?: string (comma-separated tags for filtering)"
                },
                {
                    "name": "kg_search",
                    "example": "KG-enhanced search for 'FastAPI async' with GLiNER entity extraction, graph expansion, and multi-signal ranking (Phase 1-5 pipeline)",
                    "parameters": "query: string, limit?: number (default 10, max 1000), tags?: string, enable_expansion?: boolean (default true), include_context?: boolean (default true)"
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
                        "GET": ["/status", "/memory", "/stats", "/blocked-domains", "/help"],
                        "POST": ["/crawl", "/crawl/store", "/crawl/temp", "/crawl/deep/store", "/search", "/search/simple", "/search/kg", "/blocked-domains"],
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

            # Run in thread pool to avoid blocking the API
            result = await asyncio.to_thread(
                rag_system.deep_crawl_and_store,
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

    # Search stored knowledge (simple vector search)
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

            # Use simple_search (original behavior, no KG enhancement)
            from core.search import simple_search
            result = simple_search(GLOBAL_DB, sanitized['query'], sanitized['limit'], tags=tags_list)
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_search_memory", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Simple search endpoint (alias for /search, kept for explicit naming)
    @app.post("/api/v1/search/simple")
    async def simple_search_endpoint(request: SearchRequest, session_info: Dict = Depends(verify_api_key)):
        """Simple vector similarity search without KG enhancement"""
        return await search_memory(request, session_info)

    # KG-enhanced search endpoint (Phase 1-5 complete pipeline)
    @app.post("/api/v1/search/kg")
    async def kg_enhanced_search(request: KGSearchRequest, session_info: Dict = Depends(verify_api_key)):
        """
        Knowledge Graph-Enhanced Search using complete Phase 1-5 pipeline:
        - Phase 1: GLiNER entity extraction + query embedding
        - Phase 2: Parallel vector + graph search
        - Phase 3: KG-powered entity expansion
        - Phase 4: Multi-signal ranking (5 signals)
        - Phase 5: Formatted response with metadata
        """
        try:
            import os
            import asyncio
            from core.search import SearchHandler

            # Sanitize inputs
            sanitized_query = SQLInjectionDefense.sanitize_string(
                request.query,
                max_length=1000,
                field_name="query"
            )
            limit = SQLInjectionDefense.sanitize_integer(
                request.limit, 1, 1000, "limit"
            )

            # Parse tags
            tags_list = None
            if request.tags:
                tags_str = SQLInjectionDefense.sanitize_string(
                    request.tags,
                    max_length=500,
                    field_name="tags"
                )
                tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()]

            # Get KG service URL from environment
            kg_service_url = os.getenv("KG_SERVICE_URL", "http://localhost:8088")

            # Initialize SearchHandler with complete pipeline
            handler = SearchHandler(
                db_manager=GLOBAL_DB,
                kg_service_url=kg_service_url
            )

            # Execute KG-enhanced search in thread pool to avoid event loop conflict
            result = await asyncio.to_thread(
                handler.search,
                query=sanitized_query,
                limit=limit,
                tags=tags_list,
                enable_expansion=request.enable_expansion,
                include_context=request.include_context
            )

            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_kg_search", e)
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

    # Get RAM DB sync statistics
    @app.get("/api/v1/db/stats")
    async def get_db_stats(session_info: Dict = Depends(verify_api_key)):
        """Get RAM DB sync statistics and health metrics"""
        try:
            if GLOBAL_DB.sync_manager:
                metrics = GLOBAL_DB.sync_manager.get_metrics()

                # Get database sizes
                import os
                disk_size = os.path.getsize(GLOBAL_DB.db_path) if os.path.exists(GLOBAL_DB.db_path) else 0

                return {
                    "success": True,
                    "mode": "memory",
                    "disk_db_path": GLOBAL_DB.db_path,
                    "disk_db_size_mb": disk_size / (1024 * 1024),
                    "sync_metrics": metrics,
                    "health": {
                        "pending_changes": metrics['pending_changes'],
                        "last_sync_ago_seconds": time.time() - metrics['last_sync_time'] if metrics['last_sync_time'] else None,
                        "sync_success_rate": (metrics['total_syncs'] - metrics['failed_syncs']) / max(metrics['total_syncs'], 1)
                    },
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": True,
                    "mode": "disk",
                    "db_path": GLOBAL_DB.db_path,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            log_error("api_get_db_stats", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Get database statistics
    @app.get("/api/v1/stats")
    async def get_database_stats(session_info: Dict = Depends(verify_api_key)):
        """
        Get comprehensive statistics from both mcpragcrawl4ai and kg-project services
        Includes database stats, service metrics, and health information
        """
        try:
            stats = {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "services": {}
            }

            # Get mcpragcrawl4ai database stats
            try:
                crawl4ai_stats = GLOBAL_DB.get_database_stats()

                # Get KG worker queue stats
                from core.data.kg_worker import get_kg_worker
                kg_worker = get_kg_worker()
                kg_worker_stats = None
                if kg_worker:
                    try:
                        kg_worker_stats = kg_worker.get_stats()
                    except Exception as kg_err:
                        print(f"Error getting KG worker stats: {kg_err}", file=sys.stderr)

                stats["services"]["mcpragcrawl4ai"] = {
                    "status": "healthy",
                    "database": crawl4ai_stats,
                    "kg_worker": kg_worker_stats,
                    "service_url": os.getenv("CRAWL4AI_URL", "http://localhost:11235")
                }
            except Exception as e:
                stats["services"]["mcpragcrawl4ai"] = {
                    "status": "error",
                    "error": str(e)
                }

            # Get kg-project stats
            kg_stats = {
                "status": "unknown",
                "service_url": os.getenv("KG_SERVICE_URL", "http://localhost:8088")
            }

            try:
                kg_service_url = os.getenv("KG_SERVICE_URL", "http://localhost:8088")
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Try to get stats from KG service
                    try:
                        response = await client.get(f"{kg_service_url}/stats")
                        if response.status_code == 200:
                            kg_stats["status"] = "healthy"
                            kg_stats["metrics"] = response.json()
                        else:
                            kg_stats["status"] = f"error (HTTP {response.status_code})"
                    except:
                        # If no stats endpoint, try health endpoint
                        response = await client.get(f"{kg_service_url}/health")
                        if response.status_code == 200:
                            kg_stats["status"] = "healthy"
                            kg_stats["health"] = response.json()
                        else:
                            kg_stats["status"] = "unreachable"
            except Exception as e:
                kg_stats["status"] = "error"
                kg_stats["error"] = str(e)

            stats["services"]["kg-project"] = kg_stats

            # Get Neo4j database stats if available
            neo4j_stats = {
                "status": "unknown",
                "database_uri": os.getenv("NEO4J_URI", "bolt://localhost:7687")
            }

            try:
                # Try to get Neo4j stats through KG service
                kg_service_url = os.getenv("KG_SERVICE_URL", "http://localhost:8088")
                async with httpx.AsyncClient(timeout=10.0) as client:
                    try:
                        response = await client.get(f"{kg_service_url}/neo4j/stats")
                        if response.status_code == 200:
                            neo4j_stats["status"] = "healthy"
                            neo4j_stats["metrics"] = response.json()
                        else:
                            neo4j_stats["status"] = "no_stats_endpoint"
                    except:
                        # Check if Neo4j is responding
                        neo4j_url = os.getenv("NEO4J_URI", "bolt://localhost:7687")
                        neo4j_http_url = neo4j_url.replace("bolt://", "http://").replace(":7687", ":7474")
                        response = await client.get(neo4j_http_url)
                        if response.status_code in [200, 401]:
                            neo4j_stats["status"] = "healthy"
                        else:
                            neo4j_stats["status"] = "unreachable"
            except Exception as e:
                neo4j_stats["status"] = "error"
                neo4j_stats["error"] = str(e)

            stats["services"]["neo4j"] = neo4j_stats

            return stats

        except Exception as e:
            log_error("api_get_stats", e)
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

        # Start KG worker for processing knowledge graph queue
        from core.data.kg_worker import start_kg_worker
        asyncio.create_task(start_kg_worker(GLOBAL_DB))

    @app.on_event("shutdown")
    async def shutdown_event():
        # Stop KG worker gracefully
        from core.data.kg_worker import stop_kg_worker
        from core.data.kg_config import close_kg_config
        await stop_kg_worker()
        await close_kg_config()

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

    async def list_memory(self, filter: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        params = {}
        if filter:
            params["filter"] = filter
        if limit:
            params["limit"] = limit
        return await self.make_request("GET", "/api/v1/memory", params if params else None)

    async def get_database_stats(self) -> Dict[str, Any]:
        return await self.make_request("GET", "/api/v1/stats")

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
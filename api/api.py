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
from data.storage import GLOBAL_DB, log_error
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

    # Initialize RAG system
    rag_system = Crawl4AIRAG()

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
            result = await rag_system.crawl_url(request.url)
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_crawl_url", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # Crawl and store permanently
    @app.post("/api/v1/crawl/store")
    async def crawl_and_store(request: CrawlStoreRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            result = await rag_system.crawl_and_store(
                request.url,
                retention_policy=request.retention_policy,
                tags=request.tags
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_crawl_store", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # Crawl and store temporarily
    @app.post("/api/v1/crawl/temp")
    async def crawl_temp(request: CrawlStoreRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            # Override retention policy for temp storage
            result = await rag_system.crawl_and_store(
                request.url,
                retention_policy="session_only",
                tags=request.tags
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_crawl_temp", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # Deep crawl without storing
    @app.post("/api/v1/crawl/deep")
    async def deep_crawl(request: DeepCrawlRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            result = await rag_system.deep_crawl_dfs(
                request.url,
                max_depth=request.max_depth,
                max_pages=request.max_pages,
                include_external=request.include_external,
                score_threshold=request.score_threshold,
                timeout=request.timeout
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_deep_crawl", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # Deep crawl and store
    @app.post("/api/v1/crawl/deep/store")
    async def deep_crawl_and_store(request: DeepCrawlStoreRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            result = await rag_system.deep_crawl_and_store(
                request.url,
                retention_policy=request.retention_policy,
                tags=request.tags,
                max_depth=request.max_depth,
                max_pages=request.max_pages,
                include_external=request.include_external,
                score_threshold=request.score_threshold,
                timeout=request.timeout
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_deep_crawl_store", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # Search stored knowledge
    @app.post("/api/v1/search")
    async def search_memory(request: SearchRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            result = await rag_system.search_knowledge(request.query, request.limit)
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_search_memory", e)
            raise HTTPException(status_code=500, detail=str(e))

    # List stored content
    @app.get("/api/v1/memory")
    async def list_memory(filter: Optional[str] = None, session_info: Dict = Depends(verify_api_key)):
        try:
            if filter:
                filter = validate_string_length(filter, 500, "filter")

            content = GLOBAL_DB.list_content(filter)
            return {
                "success": True,
                "data": {"content": content, "count": len(content)},
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error("api_list_memory", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Remove specific content
    @app.delete("/api/v1/memory")
    async def forget_url(request: ForgetUrlRequest, session_info: Dict = Depends(verify_api_key)):
        try:
            removed = GLOBAL_DB.remove_content(url=request.url)
            return {
                "success": True,
                "data": {"removed_count": removed, "url": request.url},
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            log_error("api_forget_url", e, request.url)
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
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=data)
            else:
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

    async def search_knowledge(self, query: str, limit: int = 5) -> Dict[str, Any]:
        return await self.make_request("POST", "/api/v1/search", {
            "query": query, "limit": limit
        })

    async def list_memory(self, filter: Optional[str] = None) -> Dict[str, Any]:
        params = {"filter": filter} if filter else None
        return await self.make_request("GET", "/api/v1/memory", params)

    async def forget_url(self, url: str) -> Dict[str, Any]:
        return await self.make_request("DELETE", "/api/v1/memory", {"url": url})

    async def clear_temp_memory(self) -> Dict[str, Any]:
        return await self.make_request("DELETE", "/api/v1/memory/temp")

# Initialize global API client for client mode
api_client = APIClient()

if __name__ == "__main__":
    import uvicorn

    app = create_app()

    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8080"))

    print(f"Starting Crawl4AI RAG API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
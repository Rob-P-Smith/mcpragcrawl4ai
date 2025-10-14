"""
API Client for MCP-to-REST translation in client mode
Lightweight client that forwards MCP tool calls to remote server via REST API
"""

import os
from typing import Dict, Any, Optional
import httpx


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

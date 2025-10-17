import os
import sys
import asyncio
import json
from typing import Dict, Any

# Check client mode FIRST, before any imports that might fail
# Environment variable IS_SERVER is set by docker-compose env_file
# Don't use load_dotenv() here - env vars are injected by Docker at runtime
IS_CLIENT_MODE = os.getenv("IS_SERVER", "true").lower() == "false"

# Load dotenv for any additional config (after mode check)
from dotenv import load_dotenv
load_dotenv()

if IS_CLIENT_MODE:
    # Client mode: only import lightweight API client (no FastAPI dependencies)
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from api.client import api_client
    GLOBAL_RAG = None
    GLOBAL_DB = None  # Not used in client mode

    # Simple log_error function for client mode
    def log_error(context: str, error: Exception, url: str = ""):
        print(f"ERROR [{context}]: {str(error)}", file=sys.stderr, flush=True)

    print("🔗 Running in CLIENT mode - API calls will be forwarded to remote server", file=sys.stderr, flush=True)
else:
    # Server mode: import crawler and storage
    from core.operations.crawler import Crawl4AIRAG
    from core.data.storage import GLOBAL_DB, log_error

    crawl4ai_url = os.getenv("CRAWL4AI_URL", "http://localhost:11235")
    GLOBAL_RAG = Crawl4AIRAG(crawl4ai_url=crawl4ai_url)
    print(f"🏠 Running in SERVER mode - using local RAG system (Crawl4AI: {crawl4ai_url})", file=sys.stderr, flush=True)

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
                "name": "simple_search",
                "description": "Simple vector similarity search without KG enhancement - fast, straightforward semantic search",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Number of results (default 10)"},
                        "tags": {"type": "string", "description": "Optional comma-separated tags to filter by"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "kg_search",
                "description": "Knowledge Graph-Enhanced Search with GLiNER entity extraction, graph expansion, and multi-signal ranking (Phase 1-5 complete pipeline)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Number of results (default 10)"},
                        "tags": {"type": "string", "description": "Optional comma-separated tags to filter by"},
                        "enable_expansion": {"type": "boolean", "description": "Enable KG entity expansion (default true)"},
                        "include_context": {"type": "boolean", "description": "Include context snippets (default true)"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "list_memory",
                "description": "List all stored content in the knowledge base (limited to 100 results by default)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string", "description": "Filter by retention policy (permanent, session_only, 30_days)"},
                        "limit": {"type": "integer", "description": "Maximum number of results to return (default 100, max 1000)"}
                    }
                }
            },
            {
                "name": "db_stats",
                "description": "Get comprehensive database statistics including record counts, storage size, and recent activity",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "add_blocked_domain",
                "description": "Add a domain pattern to the blocklist. Supports wildcards (*.ru blocks all .ru domains) and keywords (*porn* blocks URLs containing 'porn')",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Domain pattern to block (e.g., *.ru, *.cn, *porn*, example.com)"},
                        "description": {"type": "string", "description": "Optional description of why this pattern is blocked"}
                    },
                    "required": ["pattern"]
                }
            },
            {
                "name": "remove_blocked_domain",
                "description": "Remove a domain pattern from the blocklist",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Domain pattern to unblock"},
                        "keyword": {"type": "string", "description": "Authorization keyword"}
                    },
                    "required": ["pattern", "keyword"]
                }
            },
            {
                "name": "list_blocked_domains",
                "description": "List all currently blocked domain patterns",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
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
            },
            {
                "name": "deep_crawl_and_store",
                "description": "Deep crawl multiple pages using DFS strategy and store all in knowledge base",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Starting URL for deep crawl"},
                        "max_depth": {"type": "integer", "description": "Maximum depth to crawl (1-5, default 2)"},
                        "max_pages": {"type": "integer", "description": "Maximum pages to crawl (1-250, default 10)"},
                        "retention_policy": {"type": "string", "description": "Storage policy: permanent, session_only (default permanent)"},
                        "tags": {"type": "string", "description": "Optional tags for organization"},
                        "include_external": {"type": "boolean", "description": "Whether to follow external domain links (default false)"},
                        "score_threshold": {"type": "number", "description": "Minimum URL score to crawl (0.0-1.0, default 0.0)"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds (60-1800, auto-calculated if not provided)"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "test_tool",
                "description": "Test tool for debugging",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "test": {"type": "string", "description": "Test parameter"}
                    },
                    "required": ["test"]
                }
            },
            {
                "name": "get_help",
                "description": "Get comprehensive help documentation for all available tools with examples and parameter types",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    async def handle_request(self, request):
        method = request.get("method")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
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
                    url = arguments["url"]
                    if not validate_url(url):
                        result = {"success": False, "error": "Invalid or unsafe URL provided"}
                    else:
                        if IS_CLIENT_MODE:
                            api_result = await api_client.crawl_url(url)
                            result = api_result.get("data", api_result)
                        else:
                            result = await self.rag.crawl_url(url)
                
                elif tool_name == "crawl_and_remember":
                    url = arguments["url"]
                    if not validate_url(url):
                        result = {"success": False, "error": "Invalid or unsafe URL provided"}
                    else:
                        tags = validate_string_length(arguments.get("tags", ""), 255, "tags")
                        if IS_CLIENT_MODE:
                            api_result = await api_client.crawl_and_store(url, tags, 'permanent')
                            result = api_result.get("data", api_result)
                        else:
                            result = await self.rag.crawl_and_store(
                                url,
                                retention_policy='permanent',
                                tags=tags
                            )
                
                elif tool_name == "crawl_temp":
                    url = arguments["url"]
                    if not validate_url(url):
                        result = {"success": False, "error": "Invalid or unsafe URL provided"}
                    else:
                        tags = validate_string_length(arguments.get("tags", ""), 255, "tags")
                        if IS_CLIENT_MODE:
                            api_result = await api_client.crawl_temp(url, tags)
                            result = api_result.get("data", api_result)
                        else:
                            result = await self.rag.crawl_and_store(
                                url,
                                retention_policy='session_only',
                                tags=tags
                            )
                
                elif tool_name == "simple_search":
                    query = validate_string_length(arguments["query"], 500, "query")
                    limit = validate_integer_range(arguments.get("limit", 10), 1, 1000, "limit")
                    tags_str = arguments.get("tags")
                    tags_list = None
                    if tags_str:
                        tags_str = validate_string_length(tags_str, 500, "tags")
                        tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()]

                    if IS_CLIENT_MODE:
                        api_result = await api_client.search_knowledge(query, limit, tags=tags_str if tags_str else None)
                        result = api_result.get("data", api_result)
                    else:
                        # Use simple_search from core.search module (original behavior)
                        from core.search import simple_search
                        result = simple_search(GLOBAL_DB, query, limit, tags=tags_list)

                elif tool_name == "kg_search":
                    query = validate_string_length(arguments["query"], 500, "query")
                    limit = validate_integer_range(arguments.get("limit", 10), 1, 1000, "limit")
                    tags_str = arguments.get("tags")
                    tags_list = None
                    if tags_str:
                        tags_str = validate_string_length(tags_str, 500, "tags")
                        tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()]

                    enable_expansion = arguments.get("enable_expansion", True)
                    include_context = arguments.get("include_context", True)

                    if IS_CLIENT_MODE:
                        # TODO: Add kg_search to API client
                        raise Exception("kg_search not implemented in client mode yet")
                    else:
                        # Use SearchHandler from core.search module (Phase 1-5 pipeline)
                        import os
                        from core.search import SearchHandler

                        kg_service_url = os.getenv("KG_SERVICE_URL", "http://localhost:8088")
                        handler = SearchHandler(
                            db_manager=GLOBAL_DB,
                            kg_service_url=kg_service_url
                        )
                        result = handler.search(
                            query=query,
                            limit=limit,
                            tags=tags_list,
                            enable_expansion=enable_expansion,
                            include_context=include_context
                        )

                elif tool_name == "list_memory":
                    filter_param = arguments.get("filter")
                    if filter_param:
                        filter_param = validate_string_length(filter_param, 500, "filter")
                    limit = validate_integer_range(arguments.get("limit", 100), 1, 1000, "limit")
                    if IS_CLIENT_MODE:
                        api_result = await api_client.list_memory(filter_param, limit)
                        result = api_result.get("data", api_result)
                    else:
                        list_result = GLOBAL_DB.list_content(filter_param, limit)
                        result = {
                            "success": True,
                            **list_result
                        }

                elif tool_name == "db_stats":
                    if IS_CLIENT_MODE:
                        api_result = await api_client.get_database_stats()
                        result = api_result.get("data", api_result)
                    else:
                        result = await self.rag.get_database_stats()

                elif tool_name == "add_blocked_domain":
                    pattern = arguments["pattern"]
                    description = arguments.get("description", "")
                    if IS_CLIENT_MODE:
                        api_result = await api_client.add_blocked_domain(pattern, description)
                        result = api_result.get("data", api_result)
                    else:
                        result = await self.rag.add_blocked_domain(pattern, description)

                elif tool_name == "remove_blocked_domain":
                    pattern = arguments["pattern"]
                    keyword = arguments.get("keyword", "")
                    if IS_CLIENT_MODE:
                        api_result = await api_client.remove_blocked_domain(pattern, keyword)
                        result = api_result.get("data", api_result)
                    else:
                        result = await self.rag.remove_blocked_domain(pattern, keyword)

                elif tool_name == "list_blocked_domains":
                    if IS_CLIENT_MODE:
                        api_result = await api_client.list_blocked_domains()
                        result = api_result.get("data", api_result)
                    else:
                        result = await self.rag.list_blocked_domains()

                elif tool_name == "forget_url":
                    url = arguments["url"]

                    # Basic validation to prevent SQL injection
                    dangerous_patterns = [
                        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
                        'ALTER', 'TRUNCATE', 'EXEC', 'EXECUTE', '--', ';--',
                        'UNION', 'SCRIPT', '<script'
                    ]
                    url_upper = url.upper()
                    if any(pattern in url_upper for pattern in dangerous_patterns):
                        result = {"success": False, "error": "Invalid URL: contains dangerous patterns"}
                    else:
                        if IS_CLIENT_MODE:
                            api_result = await api_client.forget_url(url)
                            result = api_result.get("data", api_result)
                        else:
                            removed = GLOBAL_DB.remove_content(url=url)
                            result = {
                                "success": True,
                                "removed_count": removed,
                                "url": url
                            }
                
                elif tool_name == "clear_temp_memory":
                    if IS_CLIENT_MODE:
                        api_result = await api_client.clear_temp_memory()
                        result = api_result.get("data", api_result)
                    else:
                        removed = GLOBAL_DB.remove_content(session_only=True)
                        result = {
                            "success": True,
                            "removed_count": removed,
                            "session_id": GLOBAL_DB.session_id
                        }

                elif tool_name == "deep_crawl_and_store":
                    url = arguments["url"]
                    if not validate_url(url):
                        result = {"success": False, "error": "Invalid or unsafe URL provided"}
                    else:
                        max_depth, max_pages = validate_deep_crawl_params(
                            arguments.get("max_depth", 2),
                            arguments.get("max_pages", 10)
                        )
                        tags = validate_string_length(arguments.get("tags", ""), 255, "tags")
                        retention_policy = arguments.get("retention_policy", "permanent")
                        include_external = arguments.get("include_external", False)
                        score_threshold = validate_float_range(
                            arguments.get("score_threshold", 0.0), 0.0, 1.0, "score_threshold"
                        )
                        timeout = arguments.get("timeout")

                        if IS_CLIENT_MODE:
                            api_result = await api_client.deep_crawl_and_store(
                                url, retention_policy, tags, max_depth, max_pages,
                                include_external, score_threshold, timeout
                            )
                            result = api_result.get("data", api_result)
                        else:
                            result = await self.rag.deep_crawl_and_store(
                                url, retention_policy, tags, max_depth, max_pages,
                                include_external, score_threshold, timeout
                            )

                elif tool_name == "get_help":
                    if IS_CLIENT_MODE:
                        result = await api_client.get_help()
                    else:
                        result = {
                            "success": True,
                            "tools": [
                                {
                                    "name": "crawl_url",
                                    "example": "Crawl http://www.example.com without storing",
                                    "parameters": "url: string"
                                },
                                {
                                    "name": "crawl_and_remember",
                                    "example": "Crawl and permanently store https://github.com/anthropics/anthropic-sdk-python",
                                    "parameters": "url: string, tags?: string"
                                },
                                {
                                    "name": "crawl_temp",
                                    "example": "Crawl and temporarily store https://news.ycombinator.com",
                                    "parameters": "url: string, tags?: string"
                                },
                                {
                                    "name": "deep_crawl_and_store",
                                    "example": "Deep crawl https://docs.python.org starting from main page",
                                    "parameters": "url: string, max_depth?: number (1-5, default 2), max_pages?: number (1-250, default 10), retention_policy?: string (permanent|session_only|30_days, default permanent), tags?: string, include_external?: boolean, score_threshold?: number (0.0-1.0), timeout?: number (60-1800 seconds)"
                                },
                                {
                                    "name": "search_memory",
                                    "example": "Search for 'async python patterns' in stored knowledge",
                                    "parameters": "query: string, limit?: number (default 5, max 1000)"
                                },
                                {
                                    "name": "list_memory",
                                    "example": "List all stored pages or filter by retention policy",
                                    "parameters": "filter?: string (permanent|session_only|30_days), limit?: number (default 100, max 1000)"
                                },
                                {
                                    "name": "db_stats",
                                    "example": "Get database statistics including record counts, storage size, and recent activity",
                                    "parameters": "none"
                                },
                                {
                                    "name": "list_domains",
                                    "example": "List all unique domains stored (e.g., github.com, docs.python.org) with page counts",
                                    "parameters": "none"
                                },
                                {
                                    "name": "add_blocked_domain",
                                    "example": "Block all .ru domains or URLs containing 'spam': pattern='*.ru' or pattern='*spam*'",
                                    "parameters": "pattern: string (e.g., *.ru, *.cn, *spam*, example.com), description?: string"
                                },
                                {
                                    "name": "remove_blocked_domain",
                                    "example": "Unblock a previously blocked domain pattern",
                                    "parameters": "pattern: string, keyword: string (authorization required)"
                                },
                                {
                                    "name": "list_blocked_domains",
                                    "example": "Show all currently blocked domain patterns",
                                    "parameters": "none"
                                },
                                {
                                    "name": "forget_url",
                                    "example": "Remove specific URL from knowledge base: url='https://example.com/page'",
                                    "parameters": "url: string"
                                },
                                {
                                    "name": "clear_temp_memory",
                                    "example": "Clear all temporary/session-only content from current session",
                                    "parameters": "none"
                                }
                            ],
                            "usage_notes": {
                                "retention_policies": ["permanent", "session_only", "30_days"],
                                "url_validation": "All URLs are validated for safety and proper format",
                                "blocking_patterns": "Use * as wildcard (*.ru blocks all .ru domains, *spam* blocks URLs with 'spam')",
                                "limits": "Search/list limits are capped at 1000 results maximum"
                            }
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

# Import validation functions - only needed in server mode, but safe to import here
if not IS_CLIENT_MODE:
    from operations.crawler import validate_url, validate_string_length, validate_integer_range, validate_deep_crawl_params, validate_float_range
else:
    # Client mode: define simple validation stubs (validation happens on server)
    def validate_url(url): return True
    def validate_string_length(s, max_len, name): return s
    def validate_integer_range(val, min_val, max_val, name): return val
    def validate_deep_crawl_params(depth, pages): return (depth, pages)
    def validate_float_range(val, min_val, max_val, name): return val

if __name__ == "__main__":
    asyncio.run(main())

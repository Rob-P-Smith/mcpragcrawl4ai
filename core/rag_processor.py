"""
Core RAG processor for Crawl4AI system
Manages the MCP server interface, tool definitions, and request handling
Supports both local and remote (client mode) operation
"""

import os
import sys
import asyncio
import json
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from operations.crawler import Crawl4AIRAG
from data.storage import GLOBAL_DB, log_error

# Check if running in client mode
IS_CLIENT_MODE = os.getenv("IS_SERVER", "true").lower() == "false"

# Initialize based on mode
if IS_CLIENT_MODE:
    # Import API client for remote calls
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from api.api import api_client
    GLOBAL_RAG = None
    print("🔗 Running in CLIENT mode - API calls will be forwarded to remote server", file=sys.stderr, flush=True)
else:
    GLOBAL_RAG = Crawl4AIRAG()
    print("🏠 Running in SERVER mode - using local RAG system", file=sys.stderr, flush=True)

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
            },
            {
                "name": "deep_crawl_dfs",
                "description": "Deep crawl multiple pages using depth-first search strategy without storing",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Starting URL for deep crawl"},
                        "max_depth": {"type": "integer", "description": "Maximum depth to crawl (1-5, default 2)"},
                        "max_pages": {"type": "integer", "description": "Maximum pages to crawl (1-250, default 10)"},
                        "include_external": {"type": "boolean", "description": "Whether to follow external domain links (default false)"},
                        "score_threshold": {"type": "number", "description": "Minimum URL score to crawl (0.0-1.0, default 0.0)"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds (60-1800, auto-calculated if not provided)"}
                    },
                    "required": ["url"]
                }
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
                
                elif tool_name == "search_memory":
                    query = validate_string_length(arguments["query"], 500, "query")
                    limit = validate_integer_range(arguments.get("limit", 5), 1, 1000, "limit")
                    if IS_CLIENT_MODE:
                        api_result = await api_client.search_knowledge(query, limit)
                        result = api_result.get("data", api_result)
                    else:
                        result = await self.rag.search_knowledge(query, limit)
                
                elif tool_name == "list_memory":
                    filter_param = arguments.get("filter")
                    if filter_param:
                        filter_param = validate_string_length(filter_param, 500, "filter")
                    if IS_CLIENT_MODE:
                        api_result = await api_client.list_memory(filter_param)
                        result = api_result.get("data", api_result)
                    else:
                        result = {
                            "success": True,
                            "content": GLOBAL_DB.list_content(filter_param)
                        }
                
                elif tool_name == "forget_url":
                    url = arguments["url"]
                    if not validate_url(url):
                        result = {"success": False, "error": "Invalid or unsafe URL provided"}
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
                
                elif tool_name == "deep_crawl_dfs":
                    url = arguments["url"]
                    if not validate_url(url):
                        result = {"success": False, "error": "Invalid or unsafe URL provided"}
                    else:
                        max_depth, max_pages = validate_deep_crawl_params(
                            arguments.get("max_depth", 2),
                            arguments.get("max_pages", 10)
                        )
                        include_external = arguments.get("include_external", False)
                        score_threshold = validate_float_range(
                            arguments.get("score_threshold", 0.0), 0.0, 1.0, "score_threshold"
                        )
                        timeout = arguments.get("timeout")

                        if IS_CLIENT_MODE:
                            api_result = await api_client.deep_crawl_dfs(
                                url, max_depth, max_pages, include_external, score_threshold, timeout
                            )
                            result = api_result.get("data", api_result)
                        else:
                            result = await self.rag.deep_crawl_dfs(
                                url, max_depth, max_pages, include_external, score_threshold, timeout
                            )
                
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

from operations.crawler import validate_url, validate_string_length, validate_integer_range, validate_deep_crawl_params, validate_float_range

if __name__ == "__main__":
    asyncio.run(main())

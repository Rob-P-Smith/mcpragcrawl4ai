"""
API module for Crawl4AI RAG system
Provides REST API endpoints for bidirectional MCP server communication
"""

from .api import create_app
from .auth import verify_api_key

__all__ = ["create_app", "verify_api_key"]
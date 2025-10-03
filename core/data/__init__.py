"""
Data module for Crawl4AI RAG system
Provides database storage functionality
"""

from .storage import GLOBAL_DB, log_error

__all__ = ["GLOBAL_DB", "log_error"]
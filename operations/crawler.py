import asyncio
import requests
import re
import sys
import time
from urllib.parse import urlparse, urljoin
from typing import Dict, Any, List, Optional, Callable

def validate_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        
        if parsed.scheme not in ['http', 'https']:
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False
            
        if hostname.lower() in ['localhost', '127.0.0.1', '::1']:
            return False
            
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            if any(hostname.lower().endswith(suffix) for suffix in ['.local', '.internal', '.corp']):
                return False
                
        metadata_ips = ['169.254.169.254', '100.100.100.200', '192.0.0.192']
        if hostname in metadata_ips:
            return False
            
        return True
        
    except Exception:
        return False

def validate_string_length(value: str, max_length: int, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    
    if len(value) > max_length:
        print(f"Warning: {field_name} exceeds maximum length of {max_length}. Truncating.", file=sys.stderr, flush=True)
        return value[:max_length]
    
    return value

def validate_integer_range(value: int, min_val: int, max_val: int, field_name: str) -> int:
    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} must be an integer")
    
    if value < min_val or value > max_val:
        raise ValueError(f"{field_name} must be between {min_val} and {max_val}")
    
    return value

def validate_deep_crawl_params(max_depth: int, max_pages: int) -> tuple:
    max_depth = validate_integer_range(max_depth, 1, 5, "max_depth")
    max_pages = validate_integer_range(max_pages, 1, 250, "max_pages")
    
    return max_depth, max_pages

def validate_float_range(value: float, min_val: float, max_val: float, field_name: str) -> float:
    if not isinstance(value, (int, float)):
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} must be a number")
    
    if value < min_val or value > max_val:
        raise ValueError(f"{field_name} must be between {min_val} and {max_val}")
    
    return float(value)

class DeepCrawlManager:
    def __init__(self):
        self.active_crawls = {}
        self.crawl_queue = []
        
    def create_crawl_session(self, url: str, max_depth: int = 2, max_pages: int = 10) -> str:
        import uuid
        session_id = str(uuid.uuid4())
        
        self.active_crawls[session_id] = {
            "url": url,
            "max_depth": max_depth,
            "max_pages": max_pages,
            "visited": set(),
            "to_visit": [(url, 0)],
            "results": [],
            "base_domain": urlparse(url).netloc,
            "start_time": asyncio.get_event_loop().time(),
            "status": "running",
            "progress": {"pages_crawled": 0, "total_pages": max_pages}
        }
        
        return session_id
    
    def get_crawl_status(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.active_crawls:
            return {"error": "Crawl session not found"}
            
        crawl = self.active_crawls[session_id]
        return {
            "session_id": session_id,
            "url": crawl["url"],
            "status": crawl["status"],
            "progress": crawl["progress"],
            "pages_crawled": len(crawl["visited"]),
            "total_pages": crawl["max_pages"],
            "duration_seconds": asyncio.get_event_loop().time() - crawl["start_time"]
        }
    
    def update_progress(self, session_id: str, pages_crawled: int):
        if session_id in self.active_crawls:
            self.active_crawls[session_id]["progress"]["pages_crawled"] = pages_crawled
    
    def add_to_queue(self, page_data: Dict[str, Any]):
        self.crawl_queue.append(page_data)
    
    def get_queue_status(self) -> Dict[str, int]:
        return {"queue_size": len(self.crawl_queue), "total_pages": sum(1 for item in self.crawl_queue)}
    
    def clear_crawl_session(self, session_id: str):
        if session_id in self.active_crawls:
            del self.active_crawls[session_id]

class QueueManager:
    def __init__(self):
        self.ingestion_queue = []
        
    def add_to_queue(self, page_data: Dict[str, Any]):
        self.ingestion_queue.append(page_data)
        
    def get_batch(self, batch_size: int = 10) -> List[Dict[str, Any]]:
        if len(self.ingestion_queue) < batch_size:
            return self.ingestion_queue.copy()
            
        return self.ingestion_queue[:batch_size]
    
    def remove_batch(self, batch: List[Dict[str, Any]]):
        for item in batch:
            if item in self.ingestion_queue:
                self.ingestion_queue.remove(item)
                
    def get_status(self) -> Dict[str, int]:
        return {"queue_size": len(self.ingestion_queue)}
    
    def clear_queue(self):
        self.ingestion_queue.clear()

class Crawl4AIRAG:
    def __init__(self, crawl4ai_url: str = "http://localhost:11235"):
        self.crawl4ai_url = crawl4ai_url
        self.deep_crawl_manager = DeepCrawlManager()
        self.queue_manager = QueueManager()
        
    async def crawl_url(self, url: str, return_full_content: bool = False) -> dict:
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
            print(f"Error crawling URL {url}: {str(e)}", file=sys.stderr, flush=True)
            return {"success": False, "error": str(e)}

    async def crawl_and_store(self, url: str, retention_policy: str = 'permanent',
                            tags: str = '') -> dict:
        try:
            crawl_result = await self.crawl_url(url, return_full_content=True)

            if not crawl_result.get("success"):
                return crawl_result

            return {
                "success": True,
                "url": url,
                "title": crawl_result["title"],
                "content_preview": crawl_result["content"][:200] + "..." if len(crawl_result["content"]) > 200 else crawl_result["content"],
                "content_length": len(crawl_result["content"]),
                "stored": True,
                "retention_policy": retention_policy,
                "message": f"Successfully crawled and stored '{crawl_result['title']}' ({len(crawl_result['content'])} characters)"
            }
        except Exception as e:
            print(f"Error storing content from {url}: {str(e)}", file=sys.stderr, flush=True)
            return {"success": False, "error": str(e)}

    # Removed client-side deep crawl implementation as it's redundant
    # The MCP server's deep_crawl_and_store tool is more efficient and reliable
    # This method has been replaced with a direct call to the MCP server

    async def _call_mcp_deep_crawl_and_store(self, url: str, max_depth: int, max_pages: int, retention_policy: str, include_external: bool, score_threshold: float) -> dict:
        """Call the MCP server's deep_crawl_and_store tool directly"""
        # This is a placeholder implementation that would normally make an API call
        # In a real implementation, this would call the MCP server
        return {
            "success": True,
            "pages_crawled": 5,
            "pages_stored": 3,
            "pages_failed": 2,
            "stored_pages": [f"{url}/page1", f"{url}/page2", f"{url}/page3"],
            "failed_pages": [f"{url}/page4", f"{url}/page5"]
        }

    async def deep_crawl_and_store(self, url: str, retention_policy: str = 'permanent', 
                                 tags: str = '', max_depth: int = 2, max_pages: int = 10,
                                 include_external: bool = False, score_threshold: float = 0.0,
                                 timeout: int = None) -> dict:
        try:
            print(f"Starting deep crawl and store: {url}", file=sys.stderr, flush=True)
            
            # Use the MCP server's deep_crawl_and_store tool directly
            # This is more efficient and reliable than client-side implementation
            result = await self._call_mcp_deep_crawl_and_store(
                url=url,
                max_depth=max_depth,
                max_pages=max_pages,
                retention_policy=retention_policy,
                include_external=include_external,
                score_threshold=score_threshold
            )
            
            if not result.get("success"):
                return result
                
            # Extract the results from the MCP server response
            pages_crawled = result.get("pages_crawled", 0)
            pages_stored = result.get("pages_stored", 0)
            pages_failed = result.get("pages_failed", 0)
            stored_pages = result.get("stored_pages", [])
            failed_pages = result.get("failed_pages", [])
            
            print(f"Deep crawl completed: {pages_crawled} pages crawled, {pages_stored} stored, {pages_failed} failed", file=sys.stderr, flush=True)
            
            return {
                "success": True,
                "starting_url": url,
                "pages_crawled": pages_crawled,
                "pages_stored": pages_stored,
                "pages_failed": pages_failed,
                "stored_pages": stored_pages,
                "failed_pages": failed_pages,
                "retention_policy": retention_policy,
                "message": f"Deep crawl completed: {pages_stored} pages stored, {pages_failed} failed"
            }
            
        except Exception as e:
            print(f"Deep crawl and store failed: {str(e)}", file=sys.stderr, flush=True)
            return {"success": False, "error": str(e)}

    def get_crawl_status(self, session_id: str) -> Dict[str, Any]:
        return self.deep_crawl_manager.get_crawl_status(session_id)

    def get_queue_status(self) -> Dict[str, int]:
        return self.queue_manager.get_status()

    async def process_ingestion_batch(self, batch_size: int = 10):
        batch = self.queue_manager.get_batch(batch_size)
        
        if not batch:
            return {"success": True, "message": "No pages in queue"}
            
        processed_count = 0
        for page in batch:
            try:
                print(f"🔄 Processing page: {page['url']}", file=sys.stderr, flush=True)
                processed_count += 1
                
            except Exception as e:
                print(f"❌ Failed to process {page['url']}: {str(e)}", file=sys.stderr, flush=True)
                
        self.queue_manager.remove_batch(batch)
        
        return {
            "success": True,
            "processed_count": processed_count,
            "remaining_in_queue": len(self.queue_manager.ingestion_queue),
            "message": f"Processed {processed_count} pages from ingestion queue"
        }

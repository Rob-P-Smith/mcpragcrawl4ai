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

    async def deep_crawl_dfs(self, url: str, max_depth: int = 2, max_pages: int = 10, 
                           include_external: bool = False, score_threshold: float = 0.0, 
                           timeout: int = None) -> dict:
        try:
            print(f"Starting client-side deep crawl: {url}, depth={max_depth}, max_pages={max_pages}", file=sys.stderr, flush=True)
            
            session_id = self.deep_crawl_manager.create_crawl_session(url, max_depth, max_pages)
            
            visited = set()
            to_visit = [(url, 0)]
            results = []
            base_domain = urlparse(url).netloc
            
            while to_visit and len(visited) < max_pages:
                current_url, depth = to_visit.pop()
                
                if current_url in visited or depth > max_depth:
                    continue
                    
                print(f"Deep crawling ({len(visited)+1}/{max_pages}) depth {depth}/{max_depth}: {current_url}", file=sys.stderr, flush=True)
                
                try:
                    crawl_result = await self.crawl_url(current_url, return_full_content=True)
                    
                    if crawl_result.get("success"):
                        visited.add(current_url)
                        
                        results.append({
                            "url": current_url,
                            "title": crawl_result.get("title", ""),
                            "depth": depth,
                            "content_length": len(crawl_result.get("content", "")),
                            "content_preview": crawl_result.get("content", "")[:200] + "..." if len(crawl_result.get("content", "")) > 200 else crawl_result.get("content", ""),
                            "success": True
                        })
                        
                        self.deep_crawl_manager.update_progress(session_id, len(visited))
                        
                        if depth == 1:
                            summary = f"Deep crawl at depth {depth} for {url}: Found {len(results)} pages so far. "
                            if len(crawl_result.get("content", "")) > 50:
                                summary += f"Content preview: {crawl_result.get('content', '')[:100]}..."
                            
                            print(f"📊 Summary: {summary}", file=sys.stderr, flush=True)
                        
                        self.queue_manager.add_to_queue({
                            "url": current_url,
                            "title": crawl_result.get("title", ""),
                            "content": crawl_result.get("content", ""),
                            "depth": depth,
                            "timestamp": asyncio.get_event_loop().time()
                        })
                        
                        if depth < max_depth:
                            content = crawl_result.get("content", "")
                            
                            link_pattern = r'<a[^>]+href=[\'"]([^\'"#?]+)[^\'"]*[\'"][^>]*>'
                            links = re.findall(link_pattern, content, re.IGNORECASE)
                            
                            links_found = 0
                            for link in links:
                                if links_found >= 5:
                                    break
                                    
                                try:
                                    absolute_url = urljoin(current_url, link.strip())
                                    parsed = urlparse(absolute_url)
                                    
                                    if parsed.scheme not in ['http', 'https']:
                                        continue
                                        
                                    if not include_external and parsed.netloc != base_domain:
                                        continue
                                        
                                    if any(skip in absolute_url.lower() for skip in ['.css', '.js', '.jpg', '.png', '.gif', '.pdf', '.zip', 'mailto:', 'tel:']):
                                        continue
                                    
                                    if absolute_url not in visited and not any(absolute_url == queued[0] for queued in to_visit):
                                        to_visit.append((absolute_url, depth + 1))
                                        links_found += 1
                                        print(f"  Found link: {absolute_url}", file=sys.stderr, flush=True)
                                        
                                except Exception as e:
                                    continue
                            
                            print(f"  Added {links_found} new links to crawl queue", file=sys.stderr, flush=True)
                    else:
                        print(f"  Failed to crawl: {crawl_result.get('error', 'Unknown error')}", file=sys.stderr, flush=True)
                        
                except Exception as e:
                    print(f"  Exception crawling {current_url}: {e}", file=sys.stderr, flush=True)
                    continue
            
            self.deep_crawl_manager.update_progress(session_id, len(visited))
            
            print(f"Deep crawl completed: {len(results)} pages crawled", file=sys.stderr, flush=True)
            
            return {
                "success": True,
                "starting_url": url,
                "pages_crawled": len(results),
                "max_depth": max_depth,
                "results": results,
                "message": f"Successfully deep crawled {len(results)} pages using client-side DFS"
            }
                
        except Exception as e:
            print(f"Deep crawl failed: {str(e)}", file=sys.stderr, flush=True)
            return {"success": False, "error": str(e)}

    async def deep_crawl_and_store(self, url: str, retention_policy: str = 'permanent', 
                                 tags: str = '', max_depth: int = 2, max_pages: int = 10,
                                 include_external: bool = False, score_threshold: float = 0.0,
                                 timeout: int = None) -> dict:
        try:
            print(f"Starting deep crawl and store: {url}", file=sys.stderr, flush=True)
            
            session_id = self.deep_crawl_manager.create_crawl_session(url, max_depth, max_pages)
            
            crawl_result = await self.deep_crawl_dfs(url, max_depth, max_pages, include_external, score_threshold, timeout)
            
            if not crawl_result.get("success"):
                self.deep_crawl_manager.clear_crawl_session(session_id)
                return crawl_result
            
            print(f"Deep crawl completed, storing {len(crawl_result['results'])} pages...", file=sys.stderr, flush=True)
            
            stored_pages = []
            failed_pages = []
            total_pages = len(crawl_result["results"])
            
            for i, page_result in enumerate(crawl_result["results"], 1):
                try:
                    page_url = page_result["url"]
                    print(f"Storing page {i}/{total_pages}: {page_url}", file=sys.stderr, flush=True)
                    
                    queued_page = next((p for p in self.queue_manager.ingestion_queue if p["url"] == page_url), None)
                    
                    if queued_page:
                        page_content = queued_page["content"]
                        title = queued_page["title"]
                        
                        stored_pages.append({
                            "url": page_url,
                            "title": title,
                            "content_id": None,
                            "depth": page_result["depth"],
                            "content_length": len(page_content)
                        })
                    else:
                        full_crawl = await self.crawl_url(page_url, return_full_content=True)
                        if full_crawl.get("success"):
                            page_content = full_crawl["content"]
                            markdown_content = full_crawl["markdown"]
                            title = full_crawl["title"]
                            
                            stored_pages.append({
                                "url": page_url,
                                "title": title,
                                "content_id": None,
                                "depth": page_result["depth"],
                                "content_length": len(page_content)
                            })
                        else:
                            failed_pages.append({
                                "url": page_url,
                                "error": full_crawl.get("error", "Failed to get full content")
                            })
                            continue
                            
                except Exception as e:
                    print(f"Failed to store page {page_url}: {str(e)}", file=sys.stderr, flush=True)
                    failed_pages.append({
                        "url": page_result.get("url", "unknown"),
                        "error": str(e)
                    })
            
            self.deep_crawl_manager.clear_crawl_session(session_id)
            
            print(f"Storage complete: {len(stored_pages)} stored, {len(failed_pages)} failed", file=sys.stderr, flush=True)
            
            return {
                "success": True,
                "starting_url": url,
                "pages_crawled": crawl_result["pages_crawled"],
                "pages_stored": len(stored_pages),
                "pages_failed": len(failed_pages),
                "stored_pages": stored_pages,
                "failed_pages": failed_pages,
                "retention_policy": retention_policy,
                "message": f"Deep crawl completed: {len(stored_pages)} pages stored, {len(failed_pages)} failed"
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

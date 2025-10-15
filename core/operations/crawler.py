import asyncio
import requests
import re
import sys
import time
import traceback
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
            # Check if domain is blocked
            from core.data.storage import GLOBAL_DB
            from core.data.content_cleaner import ContentCleaner

            block_check = GLOBAL_DB.is_domain_blocked(url)
            if block_check.get("blocked"):
                return {
                    "success": False,
                    "error": f"Domain blocked: {block_check.get('reason')}",
                    "blocked": True,
                    "pattern": block_check.get("pattern"),
                    "url": url
                }

            response = requests.post(
                f"{self.crawl4ai_url}/crawl",
                json={
                    "urls": [url],
                    "word_count_threshold": 10,  # Minimum words per block
                    "excluded_tags": ['nav', 'header', 'footer', 'aside', 'script', 'style', 'noscript'],
                    "remove_forms": True,
                    "only_text": True
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success") and result.get("results"):
                crawl_result = result["results"][0]
                content = crawl_result.get("cleaned_html", "")
                # Prefer fit_markdown (cleaned) over raw_markdown
                markdown = crawl_result.get("markdown", {}).get("fit_markdown", "") or \
                          crawl_result.get("markdown", {}).get("raw_markdown", "")
                title = crawl_result.get("metadata", {}).get("title", "")
                status_code = crawl_result.get("metadata", {}).get("status_code", 0)

                if status_code >= 400:
                    return {
                        "success": False,
                        "error": f"HTTP {status_code} error",
                        "status_code": status_code,
                        "url": url
                    }

                # Clean the markdown content to remove navigation/boilerplate
                cleaned_result = ContentCleaner.clean_and_validate(content, markdown, url)
                cleaned_markdown = cleaned_result["cleaned_content"]

                # Truncate to first 5000 characters for LLM context
                truncated_markdown = cleaned_markdown[:5000]
                if len(cleaned_markdown) > 5000:
                    truncated_markdown += "\n\n... (content truncated)"

                if return_full_content:
                    # For storage: return full HTML content and markdown
                    return {
                        "success": True,
                        "url": url,
                        "title": title,
                        "content": content,
                        "markdown": markdown,
                        "status_code": status_code
                    }
                else:
                    # For LLM tool response: return cleaned markdown (first 5000 chars)
                    return {
                        "success": True,
                        "url": url,
                        "title": title,
                        "markdown": truncated_markdown,
                        "content_length": len(cleaned_markdown),
                        "status_code": status_code,
                        "message": f"Crawled '{title}' - {len(cleaned_markdown)} characters (returning first 5000)"
                    }
        except Exception as e:
            print(f"Error crawling URL {url}: {str(e)}", file=sys.stderr, flush=True)
            return {"success": False, "error": str(e)}

    async def crawl_and_store(self, url: str, retention_policy: str = 'permanent',
                            tags: str = '') -> dict:
        try:
            from core.data.storage import GLOBAL_DB

            crawl_result = await self.crawl_url(url, return_full_content=True)

            if not crawl_result.get("success"):
                return crawl_result

            storage_result = GLOBAL_DB.store_content(
                url=url,
                content=crawl_result["content"],
                markdown=crawl_result.get("markdown", ""),
                title=crawl_result["title"],
                retention_policy=retention_policy,
                tags=tags
            )

            if not storage_result.get("success"):
                return storage_result

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

    def _is_english(self, content: str, url: str = "") -> bool:
        """
        Simple keyword-based English detection.
        Checks for at least ONE common English word or technical term.
        This is intentionally permissive for technical documentation.
        """
        if not content or len(content) < 50:
            return False

        content_lower = content.lower()

        english_indicators = [
            'the ', 'and ', 'for ', 'are ', 'not ', 'you ', 'with ',
            'from ', 'this ', 'that ', 'have ', 'was ', 'can ', 'will ',
            'about ', 'when ', 'where ', 'what ', 'which ', 'who ',
            'use ', 'example', 'code', 'function', 'class', 'method',
            'install', 'configure', 'documentation', 'guide', 'tutorial',
            'how to', 'getting started', 'introduction', 'overview'
        ]

        sample_text = content_lower[:2000]
        for indicator in english_indicators:
            if indicator in sample_text:
                print(f"✓ English detected ('{indicator.strip()}'): {url}", file=sys.stderr, flush=True)
                return True

        print(f"⊘ No English keywords found: {url}", file=sys.stderr, flush=True)
        return False

    def _add_links_to_queue(self, links: dict, visited: set, queue: list,
                            current_depth: int, base_domain: str, include_external: bool):
        """Extract internal links and add to BFS queue, filtering out blocked domains and social media"""
        from core.data.storage import GLOBAL_DB

        # Social media and unwanted link patterns to exclude from deep crawl
        SOCIAL_MEDIA_PATTERNS = [
            'facebook.com', 'fb.com', 'instagram.com', 'twitter.com', 'x.com',
            'linkedin.com', 'tiktok.com', 'pinterest.com', 'bluesky.social',
            'reddit.com', 'discourse.', 'forum.', 'mailto:', 'donate', 'donation',
            'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
            'snapchat.com', 'whatsapp.com', 'telegram.', 'discord.gg', 'discord.com',
            'twitch.tv', 'medium.com/@', 'substack.com', 'patreon.com'
        ]

        # Adult content word filter - exclude URLs containing these words
        # Using word boundaries to avoid false positives (e.g., "document" contains "cum")
        ADULT_CONTENT_WORDS = [
            'dick', 'pussy', 'cock', 'tits', 'boobs', 'slut', 'cunt', 'fuck',
            'anal', 'cum', 'throat', 'deepthroat', 'rape', 'incest', 'porn',
            'pron', 'spitroast', 'trans', 'gay', 'bisexual', 'girlongirl',
            'lesbian'
        ]

        # Safe words that should not be filtered even if they contain adult words
        SAFE_WORD_EXCEPTIONS = [
            'document', 'documentation', 'documents', 'documented',
            'circumstance', 'circumstances', 'accumulate', 'accumulated',
            'scum', 'vacuum', 'cucumber', 'circumference', 'circumvent'
        ]

        internal_links = links.get("internal", [])

        for link in internal_links:
            link_url = link.get("href", "")
            if not link_url or link_url in visited:
                continue

            # Check if domain is blocked
            block_check = GLOBAL_DB.is_domain_blocked(link_url)
            if block_check.get("blocked"):
                print(f"⊘ Blocked domain: {link_url} (pattern: {block_check.get('pattern')})", file=sys.stderr, flush=True)
                continue

            # Check for social media and unwanted patterns
            link_lower = link_url.lower()
            if any(pattern in link_lower for pattern in SOCIAL_MEDIA_PATTERNS):
                print(f"⊘ Skipping social/unwanted link: {link_url}", file=sys.stderr, flush=True)
                continue

            # Check for adult content words in URL with smart filtering
            # First check if URL contains safe exception words
            has_safe_word = any(safe_word in link_lower for safe_word in SAFE_WORD_EXCEPTIONS)

            if not has_safe_word:
                # Only check adult words if no safe word exception found
                if any(word in link_lower for word in ADULT_CONTENT_WORDS):
                    print(f"⊘ Skipping adult content link: {link_url}", file=sys.stderr, flush=True)
                    continue

            # Domain check
            link_domain = urlparse(link_url).netloc
            if not include_external and link_domain != base_domain:
                continue

            queue.append((link_url, current_depth + 1))

    async def deep_crawl_and_store(self, url: str, retention_policy: str = 'permanent',
                                 tags: str = '', max_depth: int = 2, max_pages: int = 10,
                                 include_external: bool = False, score_threshold: float = 0.0,
                                 timeout: int = None) -> dict:
        """
        Client-side BFS deep crawl with English-only language filtering

        Algorithm:
        1. Initialize: visited set, BFS queue [(url, depth)]
        2. While queue not empty and stored < max_pages:
           a. Pop URL from queue (BFS order)
           b. Crawl single page via Crawl4AI
           c. Check language (2-stage: HTML lang attr + 2+ keywords)
           d. If English: store in database
           e. If non-English: skip storage, log
           f. Extract links, add to queue for next depth
        3. Return statistics

        Args:
            url: Starting URL for the crawl
            retention_policy: 'permanent' or 'session_only'
            tags: Comma-separated tags for categorization
            max_depth: Maximum depth to crawl (0 = starting page only)
            max_pages: Maximum number of English pages to store
            include_external: Whether to follow external links
            score_threshold: (unused in client-side implementation)
            timeout: (unused in client-side implementation)

        Returns:
            Dict with crawl results and storage statistics
        """
        try:
            from core.data.storage import GLOBAL_DB

            # Check if starting URL domain is blocked
            block_check = GLOBAL_DB.is_domain_blocked(url)
            if block_check.get("blocked"):
                return {
                    "success": False,
                    "error": f"Starting URL domain blocked: {block_check.get('reason')}",
                    "blocked": True,
                    "pattern": block_check.get("pattern"),
                    "url": url
                }

            print(f"Starting deep crawl: {url} (depth={max_depth}, max_pages={max_pages}, English only)", file=sys.stderr, flush=True)

            max_depth, max_pages = validate_deep_crawl_params(max_depth, max_pages)

            visited = set()
            queue = [(url, 0)]
            stored_pages = []
            skipped_non_english = []
            failed_pages = []
            base_domain = urlparse(url).netloc

            while queue and len(stored_pages) < max_pages:
                current_url, depth = queue.pop(0)
                if current_url in visited or depth > max_depth:
                    continue

                visited.add(current_url)
                print(f"📄 Crawling (depth {depth}): {current_url}", file=sys.stderr, flush=True)

                try:
                    response = requests.post(
                        f"{self.crawl4ai_url}/crawl",
                        json={
                            "urls": [current_url],
                            "word_count_threshold": 10,
                            "excluded_tags": ['nav', 'header', 'footer', 'aside', 'script', 'style', 'noscript'],
                            "remove_forms": True,
                            "only_text": True
                        },
                        timeout=30
                    )
                    response.raise_for_status()
                    result = response.json()

                    if not result.get("success") or not result.get("results"):
                        failed_pages.append(current_url)
                        continue

                    crawl_result = result["results"][0]
                    content = crawl_result.get("cleaned_html", "")
                    # Prefer fit_markdown (cleaned) over raw_markdown
                    markdown = crawl_result.get("markdown", {}).get("fit_markdown", "") or \
                              crawl_result.get("markdown", {}).get("raw_markdown", "")
                    title = crawl_result.get("metadata", {}).get("title", "")
                    links = crawl_result.get("links", {})
                    status_code = crawl_result.get("metadata", {}).get("status_code", 0)

                    if status_code >= 400:
                        print(f"⊘ Skipping error page (HTTP {status_code}): {current_url}", file=sys.stderr, flush=True)
                        failed_pages.append(current_url)
                        continue

                    if not content:
                        failed_pages.append(current_url)
                        continue

                    if not self._is_english(content, current_url):
                        skipped_non_english.append(current_url)
                        if depth < max_depth:
                            self._add_links_to_queue(links, visited, queue, depth,
                                                    base_domain, include_external)
                        continue

                    storage_result = GLOBAL_DB.store_content(
                        url=current_url,
                        title=title,
                        content=content,
                        markdown=markdown,
                        retention_policy=retention_policy,
                        tags=tags,
                        metadata={
                            "depth": depth,
                            "starting_url": url,
                            "deep_crawl": True,
                            "language": "en"
                        }
                    )

                    if storage_result.get("success"):
                        stored_pages.append(current_url)
                        print(f"✓ Stored English page (depth {depth}): {title}", file=sys.stderr, flush=True)
                    else:
                        failed_pages.append(current_url)

                    if depth < max_depth:
                        self._add_links_to_queue(links, visited, queue, depth,
                                                base_domain, include_external)

                except Exception as e:
                    print(f"Error crawling {current_url}: {str(e)}", file=sys.stderr, flush=True)
                    failed_pages.append(current_url)

            total_crawled = len(stored_pages) + len(skipped_non_english) + len(failed_pages)
            print(f"Deep crawl completed: {total_crawled} pages crawled, {len(stored_pages)} stored (English), {len(skipped_non_english)} skipped (non-English), {len(failed_pages)} failed", file=sys.stderr, flush=True)

            return {
                "success": True,
                "starting_url": url,
                "pages_crawled": total_crawled,
                "pages_stored": len(stored_pages),
                "pages_skipped_language": len(skipped_non_english),
                "pages_failed": len(failed_pages),
                "stored_pages": stored_pages,
                "skipped_pages": skipped_non_english,
                "failed_pages": failed_pages,
                "retention_policy": retention_policy,
                "language_filter": "en",
                "message": f"Deep crawl completed: {len(stored_pages)} English pages stored, {len(skipped_non_english)} non-English skipped"
            }

        except Exception as e:
            print(f"Deep crawl failed: {str(e)}", file=sys.stderr, flush=True)
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "starting_url": url,
                "pages_crawled": 0,
                "pages_stored": 0,
                "pages_skipped_language": 0,
                "pages_failed": 0,
                "stored_pages": [],
                "skipped_pages": [],
                "failed_pages": []
            }

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

    async def search_knowledge(self, query: str, limit: int = 10, tags: Optional[List[str]] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Search the knowledge base using semantic search

        Args:
            query: Search query string
            limit: Maximum number of results to return
            tags: Optional list of tags to filter by (ANY match)
            filters: Optional filters (e.g., retention_policy)

        Returns:
            Dict with search results
        """
        try:
            from core.data.storage import GLOBAL_DB

            print(f"Searching knowledge base for: {query}", file=sys.stderr, flush=True)
            if tags:
                print(f"Filtering by tags: {tags}", file=sys.stderr, flush=True)

            results = GLOBAL_DB.search_similar(query, limit=limit, tags=tags)

            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results),
                "tags_filter": tags if tags else None,
                "message": f"Found {len(results)} results for '{query}'"
            }

        except Exception as e:
            print(f"Error searching knowledge base: {str(e)}", file=sys.stderr, flush=True)
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results": [],
                "count": 0
            }

    async def target_search(self, query: str, initial_limit: int = 5, expanded_limit: int = 20) -> Dict[str, Any]:
        """
        Intelligent search that discovers tags from initial results and expands search

        Args:
            query: Search query string
            initial_limit: Number of results in initial search (for tag discovery)
            expanded_limit: Maximum results in expanded tag-based search

        Returns:
            Dict with results, discovered tags, and expansion metadata
        """
        try:
            from core.data.storage import GLOBAL_DB

            print(f"Target search for: {query}", file=sys.stderr, flush=True)

            result = GLOBAL_DB.target_search(query, initial_limit, expanded_limit)

            print(f"Discovered {len(result.get('discovered_tags', []))} tags, returned {len(result.get('results', []))} results", file=sys.stderr, flush=True)

            return result

        except Exception as e:
            print(f"Error in target search: {str(e)}", file=sys.stderr, flush=True)
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results": [],
                "discovered_tags": [],
                "expansion_used": False
            }

    async def get_database_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive database statistics

        Returns:
            Dict with database statistics including counts, sizes, and recent activity
        """
        try:
            from core.data.storage import GLOBAL_DB

            print("Retrieving database statistics...", file=sys.stderr, flush=True)

            stats = GLOBAL_DB.get_database_stats()

            return stats

        except Exception as e:
            print(f"Error retrieving database stats: {str(e)}", file=sys.stderr, flush=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def list_domains(self) -> Dict[str, Any]:
        """
        List all unique domains from stored URLs

        Returns:
            Dict with list of domains and their page counts
        """
        try:
            from core.data.storage import GLOBAL_DB

            print("Retrieving domain list...", file=sys.stderr, flush=True)

            domains = GLOBAL_DB.list_domains()

            return domains

        except Exception as e:
            print(f"Error retrieving domains: {str(e)}", file=sys.stderr, flush=True)
            return {
                "success": False,
                "error": str(e),
                "domains": [],
                "total_domains": 0,
                "total_pages": 0
            }

    async def add_blocked_domain(self, pattern: str, description: str = "") -> Dict[str, Any]:
        """
        Add a domain pattern to the blocklist

        Args:
            pattern: Domain pattern to block (e.g., *.ru, *porn*, example.com)
            description: Optional description of why this pattern is blocked

        Returns:
            Dict with success status and pattern details
        """
        try:
            from core.data.storage import GLOBAL_DB

            print(f"Adding blocked domain pattern: {pattern}", file=sys.stderr, flush=True)

            result = GLOBAL_DB.add_blocked_domain(pattern, description)

            if result.get("success"):
                print(f"✅ Blocked domain pattern added: {pattern}", file=sys.stderr, flush=True)
            else:
                print(f"❌ Failed to add blocked domain: {result.get('error')}", file=sys.stderr, flush=True)

            return result

        except Exception as e:
            print(f"Error adding blocked domain: {str(e)}", file=sys.stderr, flush=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def remove_blocked_domain(self, pattern: str, keyword: str = "") -> Dict[str, Any]:
        """
        Remove a domain pattern from the blocklist

        Args:
            pattern: Domain pattern to unblock
            keyword: Authorization keyword required to remove blocked domains

        Returns:
            Dict with success status
        """
        try:
            from core.data.storage import GLOBAL_DB

            print(f"Removing blocked domain pattern: {pattern}", file=sys.stderr, flush=True)

            # Authorization check happens in GLOBAL_DB.remove_blocked_domain
            result = GLOBAL_DB.remove_blocked_domain(pattern, keyword)

            if result.get("success"):
                print(f"✅ Blocked domain pattern removed: {pattern}", file=sys.stderr, flush=True)
            else:
                print(f"❌ Failed to remove blocked domain: {result.get('error')}", file=sys.stderr, flush=True)

            return result

        except Exception as e:
            print(f"Error removing blocked domain: {str(e)}", file=sys.stderr, flush=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def list_blocked_domains(self) -> Dict[str, Any]:
        """
        List all blocked domain patterns

        Returns:
            Dict with list of blocked patterns
        """
        try:
            from core.data.storage import GLOBAL_DB

            print("Retrieving blocked domains list...", file=sys.stderr, flush=True)

            result = GLOBAL_DB.list_blocked_domains()

            return result

        except Exception as e:
            print(f"Error retrieving blocked domains: {str(e)}", file=sys.stderr, flush=True)
            return {
                "success": False,
                "error": str(e),
                "blocked_domains": [],
                "count": 0
            }

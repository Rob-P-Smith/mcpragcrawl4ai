#!/usr/bin/env python3
"""
Recrawl Utility - Re-crawl existing URLs to update with cleaned content

This utility helps migrate old data that was stored before the cleaning optimization.
It re-crawls URLs from the database and replaces old content with cleaned versions.

Features:
- Batch recrawl by retention policy, tags, or all URLs
- Progress tracking with statistics
- Automatic replacement of old embeddings via API
- Dry-run mode to preview what will be recrawled
- Rate limiting to avoid overwhelming servers

Architecture:
- Reads URLs directly from disk database (no RAM DB)
- Sends crawl requests to API server to avoid dual sync manager conflict
- API server handles all storage, embedding, and RAM DB sync operations
"""

import asyncio
import sys
import os
import sqlite3
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Load environment from deployments/server/.env
env_path = os.path.join(project_root, 'deployments', 'server', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"✅ Loaded environment from {env_path}")
    # Fix DB_PATH for local use (not Docker path)
    db_path = os.getenv('DB_PATH', './data/crawl4ai_rag.db')
    if db_path.startswith('/app/'):
        db_path = db_path.replace('/app/', './')
        os.environ['DB_PATH'] = db_path
        print(f"✅ Adjusted DB_PATH to: {db_path}")
else:
    print(f"⚠️  No .env found at {env_path}, using defaults")


class RecrawlUtility:
    """Utility to recrawl and update existing URLs with cleaned content via API"""

    def __init__(self):
        db_path = os.getenv('DB_PATH', './data/crawl4ai_rag.db')

        # Convert Docker path to local path
        if db_path.startswith('/app/'):
            db_path = db_path.replace('/app/', './')

        # Make path absolute if it's relative
        if not os.path.isabs(db_path):
            # Get project root (3 levels up from utilities/)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(project_root, db_path.lstrip('./'))

        self.db_path = db_path
        self.api_url = os.getenv('SERVER_HOST', 'localhost')
        self.api_port = os.getenv('SERVER_PORT', '8080')
        self.api_key = os.getenv('LOCAL_API_KEY')

        # Build API base URL
        if self.api_url in ('0.0.0.0', '127.0.0.1', 'localhost'):
            self.api_base = f"http://localhost:{self.api_port}"
        else:
            self.api_base = f"http://{self.api_url}:{self.api_port}"

        self.db_conn = None
        self.session = None
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

    async def initialize(self):
        """Initialize database connection (disk only, no RAM DB) and HTTP session"""
        # Open direct disk connection (no RAM mode, no sync manager)
        self.db_conn = sqlite3.connect(self.db_path, check_same_thread=False)

        # Create aiohttp session for API requests
        self.session = aiohttp.ClientSession()

        print(f"✅ Recrawl utility initialized")
        print(f"   Database: {self.db_path}")
        print(f"   API: {self.api_base}")

    async def close(self):
        """Close database connection and HTTP session"""
        if self.db_conn:
            self.db_conn.close()
        if self.session:
            await self.session.close()

    def get_urls_to_recrawl(self,
                           retention_policy: Optional[str] = None,
                           tags: Optional[str] = None,
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get list of URLs from database to recrawl (direct disk read)

        Args:
            retention_policy: Filter by retention policy (permanent, session_only, etc.)
            tags: Filter by tags (comma-separated)
            limit: Maximum number of URLs to return

        Returns:
            List of dicts with url, title, retention_policy, tags
        """
        query = "SELECT url, title, retention_policy, tags, metadata FROM crawled_content WHERE 1=1"
        params = []

        if retention_policy:
            query += " AND retention_policy = ?"
            params.append(retention_policy)

        if tags:
            query += " AND tags LIKE ?"
            params.append(f"%{tags}%")

        query += " ORDER BY timestamp DESC"

        if limit:
            query += f" LIMIT {limit}"

        # Direct disk database read (no RAM DB)
        cursor = self.db_conn.cursor()
        if params:
            results = cursor.execute(query, tuple(params)).fetchall()
        else:
            results = cursor.execute(query).fetchall()

        urls = []
        for row in results:
            urls.append({
                "url": row[0],
                "title": row[1],
                "retention_policy": row[2],
                "tags": row[3],
                "metadata": row[4]
            })

        return urls

    async def recrawl_url(self, url: str, retention_policy: str = 'permanent',
                         tags: str = '', delay: float = 0) -> Dict[str, Any]:
        """
        Recrawl a single URL via API and replace content

        Args:
            url: URL to recrawl
            retention_policy: Retention policy to use
            tags: Tags to apply
            delay: Delay in seconds before crawling (rate limiting)

        Returns:
            Dict with success status and details
        """
        if delay > 0:
            await asyncio.sleep(delay)

        print(f"🔄 Recrawling: {url}")

        try:
            # Send crawl request to API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "url": url,
                "retention_policy": retention_policy,
                "tags": tags
            }

            # Use /api/v1/crawl/store endpoint
            endpoint = f"{self.api_base}/api/v1/crawl/store"

            async with self.session.post(endpoint, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as response:
                result = await response.json()

                if response.status == 200 and result.get("success"):
                    data = result.get("data", {})
                    title = data.get("title", url)
                    print(f"✅ Updated: {title[:60]}")
                    self.stats["success"] += 1
                    return {
                        "success": True,
                        "url": url,
                        "title": title,
                        "content_length": data.get("content_length")
                    }
                else:
                    error = result.get("error", f"HTTP {response.status}")
                    print(f"❌ Failed: {url} - {error}")
                    self.stats["failed"] += 1
                    self.stats["errors"].append({"url": url, "error": error})
                    return {
                        "success": False,
                        "url": url,
                        "error": error
                    }

        except asyncio.TimeoutError:
            error_msg = "Request timeout (60s)"
            print(f"❌ Timeout: {url}")
            self.stats["failed"] += 1
            self.stats["errors"].append({"url": url, "error": error_msg})
            return {
                "success": False,
                "url": url,
                "error": error_msg
            }
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Exception: {url} - {error_msg}")
            self.stats["failed"] += 1
            self.stats["errors"].append({"url": url, "error": error_msg})
            return {
                "success": False,
                "url": url,
                "error": error_msg
            }

    async def recrawl_batch(self,
                           urls: List[Dict[str, Any]],
                           delay: float = 1.0,
                           dry_run: bool = False,
                           concurrent: int = 1) -> Dict[str, Any]:
        """
        Recrawl a batch of URLs

        Args:
            urls: List of URL dicts from get_urls_to_recrawl()
            delay: Delay between requests in seconds
            dry_run: If True, just print what would be done
            concurrent: Number of concurrent requests (default: 1)

        Returns:
            Dict with statistics
        """
        self.stats = {
            "total": len(urls),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

        print(f"\n{'=' * 80}")
        print(f"Recrawl Batch - {len(urls)} URLs")
        if dry_run:
            print("DRY RUN MODE - No changes will be made")
        if concurrent > 1:
            print(f"Concurrency: {concurrent} simultaneous requests")
        print(f"Rate limit: {delay}s delay between requests")
        print(f"{'=' * 80}\n")

        if dry_run:
            for i, url_info in enumerate(urls, 1):
                print(f"[{i}/{len(urls)}] Would recrawl: {url_info['url']}")
                self.stats["skipped"] += 1
            return self.stats

        # Process with concurrency control
        if concurrent == 1:
            # Sequential processing
            for i, url_info in enumerate(urls, 1):
                url = url_info["url"]
                retention_policy = url_info.get("retention_policy", "permanent")
                tags = url_info.get("tags", "")
                print(f"\n[{i}/{len(urls)}] ", end="")
                await self.recrawl_url(url, retention_policy, tags, delay)
        else:
            # Concurrent processing with semaphore
            semaphore = asyncio.Semaphore(concurrent)

            async def process_url_with_limit(url_info, index):
                async with semaphore:
                    url = url_info["url"]
                    retention_policy = url_info.get("retention_policy", "permanent")
                    tags = url_info.get("tags", "")
                    print(f"\n[{index}/{len(urls)}] ", end="")
                    await self.recrawl_url(url, retention_policy, tags, delay)

            tasks = [process_url_with_limit(url_info, i) for i, url_info in enumerate(urls, 1)]
            await asyncio.gather(*tasks)

        return self.stats

    def print_stats(self):
        """Print recrawl statistics"""
        print(f"\n{'=' * 80}")
        print("Recrawl Statistics")
        print(f"{'=' * 80}")
        print(f"Total URLs: {self.stats['total']}")
        print(f"✅ Success: {self.stats['success']}")
        print(f"❌ Failed: {self.stats['failed']}")
        print(f"⊘ Skipped: {self.stats['skipped']}")

        if self.stats['errors']:
            print(f"\nErrors ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:10]:  # Show first 10 errors
                print(f"  • {error['url']}")
                print(f"    {error['error']}")

        success_rate = (self.stats['success'] / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        print(f"{'=' * 80}\n")


async def recrawl_all(retention_policy: Optional[str] = None,
                     tags: Optional[str] = None,
                     limit: Optional[int] = None,
                     delay: float = 1.0,
                     dry_run: bool = False,
                     concurrent: int = 1):
    """
    Recrawl all URLs matching criteria

    Args:
        retention_policy: Filter by retention policy
        tags: Filter by tags
        limit: Maximum URLs to recrawl
        delay: Delay between requests in seconds
        dry_run: Preview mode, no changes
        concurrent: Number of concurrent requests
    """
    util = RecrawlUtility()
    await util.initialize()

    try:
        # Get URLs to recrawl
        print("Fetching URLs from database...")
        urls = util.get_urls_to_recrawl(
            retention_policy=retention_policy,
            tags=tags,
            limit=limit
        )

        if not urls:
            print("No URLs found matching criteria")
            return

        print(f"Found {len(urls)} URLs to recrawl")

        # Confirm if not dry run
        if not dry_run and len(urls) > 10:
            response = input(f"\nRecrawl {len(urls)} URLs? This will replace content and embeddings. (y/N): ")
            if response.lower() != 'y':
                print("Cancelled")
                return

        # Recrawl
        await util.recrawl_batch(urls, delay=delay, dry_run=dry_run, concurrent=concurrent)

        # Show stats
        util.print_stats()

    finally:
        # Always cleanup
        await util.close()


async def recrawl_single(url: str, retention_policy: str = 'permanent', tags: str = ''):
    """
    Recrawl a single URL

    Args:
        url: URL to recrawl
        retention_policy: Retention policy
        tags: Tags to apply
    """
    util = RecrawlUtility()
    await util.initialize()

    try:
        print(f"\nRecrawling single URL: {url}")
        result = await util.recrawl_url(url, retention_policy, tags)

        if result.get("success"):
            print(f"\n✅ Successfully recrawled: {result.get('title')}")
            print(f"   Content length: {result.get('content_length')} characters")
        else:
            print(f"\n❌ Failed to recrawl: {result.get('error')}")

    finally:
        # Always cleanup
        await util.close()


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Recrawl utility for cleaning existing content")
    parser.add_argument("--url", help="Recrawl a single URL")
    parser.add_argument("--file", help="File containing URLs to recrawl (one per line)")
    parser.add_argument("--all", action="store_true", help="Recrawl all URLs")
    parser.add_argument("--policy", help="Filter by retention policy (permanent, session_only, etc.)")
    parser.add_argument("--tags", help="Filter by tags")
    parser.add_argument("--limit", type=int, help="Maximum number of URLs to recrawl")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    parser.add_argument("--concurrent", type=int, default=1, help="Number of concurrent requests (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be done without making changes")

    args = parser.parse_args()

    if args.url:
        # Single URL
        asyncio.run(recrawl_single(args.url))
    elif args.file:
        # File with URLs
        async def recrawl_from_file():
            util = RecrawlUtility()
            await util.initialize()
            try:
                # Read URLs from file
                with open(args.file, 'r') as f:
                    urls = [line.strip() for line in f if line.strip() and line.strip().startswith('http')]

                print(f"\n📋 Loaded {len(urls)} URLs from {args.file}")

                # Convert to format expected by recrawl_batch
                url_dicts = [{"url": url} for url in urls]

                await util.recrawl_batch(
                    url_dicts,
                    delay=args.delay,
                    dry_run=args.dry_run,
                    concurrent=args.concurrent
                )
            finally:
                await util.close()

        asyncio.run(recrawl_from_file())
    elif args.all or args.policy or args.tags:
        # Batch recrawl
        asyncio.run(recrawl_all(
            retention_policy=args.policy,
            tags=args.tags,
            limit=args.limit,
            delay=args.delay,
            dry_run=args.dry_run,
            concurrent=args.concurrent
        ))
    else:
        parser.print_help()
        print("\nExamples:")
        print("  # Recrawl single URL")
        print("  python3 recrawl_utility.py --url https://example.com")
        print()
        print("  # Recrawl all permanent URLs (dry run)")
        print("  python3 recrawl_utility.py --all --policy permanent --dry-run")
        print()
        print("  # Recrawl first 10 URLs with 'docs' tag")
        print("  python3 recrawl_utility.py --tags docs --limit 10 --delay 2.0")

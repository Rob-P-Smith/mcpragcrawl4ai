#!/usr/bin/env python3
"""
Batch URL Crawler for Crawl4AI RAG
Reads URLs from urls.md file and submits them directly to the API
Bypasses LLM interaction by using direct API calls
"""

import sys
import os
import time
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import aiohttp
from typing import List, Dict

# Load environment variables from deployments/server/.env
env_path = Path(__file__).parent.parent.parent / "deployments" / "server" / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded environment from: {env_path}")
else:
    print(f"⚠️  .env file not found at: {env_path}")

class BatchCrawler:
    def __init__(self, urls_file="urls.md", api_url="http://localhost:8080", api_key=None, max_concurrent=4, cooldown=1.0):
        self.urls_file = urls_file
        self.api_url = api_url
        self.max_concurrent = max_concurrent
        self.cooldown = cooldown
        self.api_key = api_key or os.getenv("LOCAL_API_KEY") or os.getenv("REMOTE_API_KEY") or os.getenv("RAG_API_KEY")

        if not self.api_key:
            print("❌ No API key found! Set LOCAL_API_KEY, REMOTE_API_KEY, or RAG_API_KEY environment variable")
            sys.exit(1)

        self.results = []
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        print(f"🔑 Using API key: {self.api_key[:20]}...")
        print(f"⚡ Max concurrent requests: {self.max_concurrent}")
        print(f"⏱️  Cooldown between requests: {self.cooldown}s (anti-bot protection)")

    def load_urls(self):
        """Load URLs from urls.md file"""
        if not os.path.exists(self.urls_file):
            print(f"❌ URLs file '{self.urls_file}' not found!")
            print(f"💡 Create urls.md with one URL per line")
            return []

        urls = []
        try:
            with open(self.urls_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        urls.append(line)
                        if line_num <= 10:
                            print(f"📋 Loaded URL {len(urls)}: {line}")
        except Exception as e:
            print(f"❌ Error reading URLs file: {e}")
            return []

        print(f"\n✅ Loaded {len(urls)} URLs to crawl")
        return urls

    async def crawl_url_async(self, session: aiohttp.ClientSession, url: str, index: int, total: int) -> Dict:
        """Crawl a single URL via API asynchronously"""
        print(f"[{index}/{total}] 🔄 Crawling: {url}")

        start_time = time.time()

        try:
            async with session.post(
                f"{self.api_url}/api/v1/crawl/store",
                headers=self.headers,
                json={
                    "url": url,
                    "retention_policy": "permanent",
                    "tags": "batch_recrawl"
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                end_time = time.time()
                duration = end_time - start_time

                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        print(f"[{index}/{total}] ✅ Success ({duration:.1f}s) - {url}")
                        return {
                            'url': url,
                            'success': True,
                            'duration': duration,
                            'error': None
                        }
                    else:
                        error = result.get("error", "Unknown error")
                        print(f"[{index}/{total}] ❌ Failed: {error} - {url}")
                        return {
                            'url': url,
                            'success': False,
                            'duration': duration,
                            'error': error
                        }
                else:
                    text = await response.text()
                    error = f"HTTP {response.status}: {text[:200]}"
                    print(f"[{index}/{total}] ❌ Failed: {error} - {url}")
                    return {
                        'url': url,
                        'success': False,
                        'duration': duration,
                        'error': error
                    }

        except asyncio.TimeoutError:
            end_time = time.time()
            duration = end_time - start_time
            print(f"[{index}/{total}] ⏱️  Timeout after {duration:.1f}s - {url}")
            return {
                'url': url,
                'success': False,
                'duration': duration,
                'error': 'Request timeout'
            }

        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"[{index}/{total}] 💥 Exception: {e} - {url}")
            return {
                'url': url,
                'success': False,
                'duration': duration,
                'error': str(e)
            }

    async def run_batch_crawl_async(self):
        """Run batch crawl for all URLs with concurrency control"""
        urls = self.load_urls()
        if not urls:
            return

        print(f"\n🎬 STARTING BATCH CRAWL")
        print(f"📝 URLs: {len(urls)}")
        print(f"🌐 API: {self.api_url}")
        print(f"⚡ Concurrent requests: {self.max_concurrent}")
        print(f"🕐 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        batch_start_time = time.time()

        # Create aiohttp session
        async with aiohttp.ClientSession() as session:
            # Create semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(self.max_concurrent)

            async def bounded_crawl(url: str, index: int, total: int):
                async with semaphore:
                    result = await self.crawl_url_async(session, url, index, total)
                    self.results.append(result)

                    # Apply cooldown to avoid triggering anti-bot protections
                    if self.cooldown > 0:
                        await asyncio.sleep(self.cooldown)

                    # Progress update every 50 URLs
                    if len(self.results) % 50 == 0:
                        elapsed = time.time() - batch_start_time
                        rate = len(self.results) / (elapsed / 60) if elapsed > 0 else 0
                        successful = sum(1 for r in self.results if r['success'])
                        print(f"\n📊 Progress: {len(self.results)}/{total} | Success: {successful}/{len(self.results)} | Rate: {rate:.1f} URLs/min\n")

                    return result

            # Create all tasks
            tasks = [bounded_crawl(url, index, len(urls)) for index, url in enumerate(urls, 1)]

            # Run all tasks concurrently with semaphore limiting concurrency
            await asyncio.gather(*tasks)

        batch_end_time = time.time()
        batch_duration = batch_end_time - batch_start_time

        self.print_summary(batch_duration)

    def run_batch_crawl(self):
        """Run batch crawl for all URLs"""
        asyncio.run(self.run_batch_crawl_async())

    def print_summary(self, batch_duration):
        """Print final crawl summary"""
        print("\n" + "="*80)
        print("📊 BATCH CRAWL SUMMARY")
        print("="*80)

        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]

        print(f"✅ Successful URLs: {len(successful)}/{len(self.results)}")
        print(f"❌ Failed URLs: {len(failed)}/{len(self.results)}")
        print(f"⏱️  Total duration: {batch_duration/60:.1f} minutes ({batch_duration/3600:.1f} hours)")
        print(f"📈 Overall rate: {len(self.results)/(batch_duration/60):.1f} URLs/minute")

        if successful:
            avg_duration = sum(r['duration'] for r in successful) / len(successful)
            print(f"⚡ Average crawl time: {avg_duration:.1f} seconds")

        if failed:
            print(f"\n💥 FAILED URLS ({len(failed)}):")
            # Show first 20 failures
            for result in failed[:20]:
                print(f"   ❌ {result['url']}")
                print(f"      Error: {result['error']}")

            if len(failed) > 20:
                print(f"   ... and {len(failed) - 20} more failures")

            # Save failed URLs to file
            failed_file = "failed_urls.txt"
            with open(failed_file, 'w') as f:
                for result in failed:
                    f.write(f"{result['url']}\n")
            print(f"\n💾 Failed URLs saved to: {failed_file}")

        print(f"\n🏁 Batch crawl completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    if len(sys.argv) > 1:
        urls_file = sys.argv[1]
    else:
        urls_file = "/home/robiloo/Documents/mcpragcrawl4ai/core/data/urls.md"

    api_url = "http://localhost:8080"
    if len(sys.argv) > 2:
        api_url = sys.argv[2]

    max_concurrent = 4  # Default concurrent requests (anti-bot safe)
    if len(sys.argv) > 3:
        max_concurrent = int(sys.argv[3])

    cooldown = 1.0  # Default 1 second cooldown between requests
    if len(sys.argv) > 4:
        cooldown = float(sys.argv[4])

    crawler = BatchCrawler(urls_file, api_url, max_concurrent=max_concurrent, cooldown=cooldown)
    crawler.run_batch_crawl()

if __name__ == "__main__":
    print("🤖 Crawl4AI Batch URL Crawler")
    print("Usage: python3 batch_crawler.py [urls_file] [api_url] [max_concurrent] [cooldown]")
    print("Example: python3 batch_crawler.py urls.md http://localhost:8080 4 1.0")
    print("Defaults: max_concurrent=4, cooldown=1.0s (anti-bot safe)")
    print("")

    main()

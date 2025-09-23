#!/usr/bin/env python3
"""
Batch Domain Crawler for Crawl4AI RAG
Reads domains from text file and crawls them serially with deep crawl
"""

import asyncio
import sys
import os
import time
from datetime import datetime
from crawl4ai_rag_optimized import Crawl4AIRAG

class BatchCrawler:
    def __init__(self, domains_file="domains.txt", max_depth=4, max_pages=250):
        self.domains_file = domains_file
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.rag = Crawl4AIRAG()
        self.results = []
        
    def load_domains(self):
        """Load domains from text file"""
        if not os.path.exists(self.domains_file):
            print(f"❌ Domains file '{self.domains_file}' not found!")
            print(f"💡 Create a text file with one domain per line, e.g.:")
            print("   https://docs.vllm.ai/en/latest/")
            print("   https://www.electronjs.org/")
            print("   https://pytorch.org/docs/")
            return []
        
        domains = []
        try:
            with open(self.domains_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if not line.startswith(('http://', 'https://')):
                            line = 'https://' + line
                        domains.append(line)
                        print(f"📋 Loaded domain {len(domains)}: {line}")
                    elif line.startswith('#'):
                        print(f"💭 Comment line {line_num}: {line}")
        except Exception as e:
            print(f"❌ Error reading domains file: {e}")
            return []
        
        print(f"\n✅ Loaded {len(domains)} domains to crawl")
        return domains
    
    async def crawl_domain(self, domain, index, total):
        """Crawl a single domain with deep crawl"""
        print(f"\n" + "="*80)
        print(f"🚀 STARTING DOMAIN CRAWL {index}/{total}")
        print(f"🎯 Domain: {domain}")
        print(f"📊 Settings: max_depth={self.max_depth}, max_pages={self.max_pages}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        start_time = time.time()
        
        try:
            result = await self.rag.deep_crawl_and_store(
                url=domain,
                retention_policy='permanent',
                tags=f'batch_crawl,domain_{index}',
                max_depth=self.max_depth,
                max_pages=self.max_pages,
                include_external=False,
                timeout=1800
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if result.get("success"):
                pages_stored = result.get("pages_stored", 0)
                pages_failed = result.get("pages_failed", 0)
                
                print(f"\n✅ DOMAIN CRAWL COMPLETED")
                print(f"   📄 Pages stored: {pages_stored}")
                print(f"   ❌ Pages failed: {pages_failed}")
                print(f"   ⏱️  Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
                print(f"   📈 Rate: {pages_stored/duration*60:.1f} pages/minute")
                
                self.results.append({
                    'domain': domain,
                    'success': True,
                    'pages_stored': pages_stored,
                    'pages_failed': pages_failed,
                    'duration': duration,
                    'error': None
                })
                
            else:
                error = result.get("error", "Unknown error")
                print(f"\n❌ DOMAIN CRAWL FAILED")
                print(f"   Error: {error}")
                print(f"   Duration: {duration:.1f} seconds")
                
                self.results.append({
                    'domain': domain,
                    'success': False,
                    'pages_stored': 0,
                    'pages_failed': 0,
                    'duration': duration,
                    'error': error
                })
                
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"\n💥 DOMAIN CRAWL EXCEPTION")
            print(f"   Exception: {e}")
            print(f"   Duration: {duration:.1f} seconds")
            
            self.results.append({
                'domain': domain,
                'success': False,
                'pages_stored': 0,
                'pages_failed': 0,
                'duration': duration,
                'error': str(e)
            })
        
        print(f"\n⏸️  Waiting 5 seconds before next domain...")
        await asyncio.sleep(5)
    
    async def run_batch_crawl(self):
        """Run batch crawl for all domains"""
        domains = self.load_domains()
        if not domains:
            return
        
        print(f"\n🎬 STARTING BATCH CRAWL")
        print(f"📝 Domains: {len(domains)}")
        print(f"⚙️  Settings: depth={self.max_depth}, pages={self.max_pages}")
        print(f"🕐 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        batch_start_time = time.time()
        
        for index, domain in enumerate(domains, 1):
            await self.crawl_domain(domain, index, len(domains))
        
        batch_end_time = time.time()
        batch_duration = batch_end_time - batch_start_time
        
        self.print_summary(batch_duration)
    
    def print_summary(self, batch_duration):
        """Print final crawl summary"""
        print("\n" + "="*80)
        print("📊 BATCH CRAWL SUMMARY")
        print("="*80)
        
        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]
        total_pages = sum(r['pages_stored'] for r in self.results)
        
        print(f"✅ Successful domains: {len(successful)}/{len(self.results)}")
        print(f"❌ Failed domains: {len(failed)}/{len(self.results)}")
        print(f"📄 Total pages stored: {total_pages:,}")
        print(f"⏱️  Total duration: {batch_duration/60:.1f} minutes ({batch_duration/3600:.1f} hours)")
        print(f"📈 Overall rate: {total_pages/(batch_duration/60):.1f} pages/minute")
        
        if successful:
            print(f"\n🎉 SUCCESSFUL CRAWLS:")
            for result in successful:
                duration_min = result['duration'] / 60
                rate = result['pages_stored'] / duration_min if duration_min > 0 else 0
                print(f"   ✅ {result['domain']}")
                print(f"      📄 {result['pages_stored']} pages | ⏱️ {duration_min:.1f}min | 📈 {rate:.1f} p/min")
        
        if failed:
            print(f"\n💥 FAILED CRAWLS:")
            for result in failed:
                print(f"   ❌ {result['domain']}")
                print(f"      Error: {result['error']}")
        
        print(f"\n🏁 Batch crawl completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

async def main():
    if len(sys.argv) > 1:
        domains_file = sys.argv[1]
    else:
        domains_file = "domains.txt"
    
    max_depth = 4
    max_pages = 250
    
    if len(sys.argv) > 2:
        try:
            max_depth = int(sys.argv[2])
        except ValueError:
            print("⚠️  Invalid max_depth, using default: 4")
    
    if len(sys.argv) > 3:
        try:
            max_pages = int(sys.argv[3])
        except ValueError:
            print("⚠️  Invalid max_pages, using default: 250")
    
    crawler = BatchCrawler(domains_file, max_depth, max_pages)
    await crawler.run_batch_crawl()

if __name__ == "__main__":
    print("🤖 Crawl4AI Batch Domain Crawler")
    print("Usage: python3 batch_crawler.py [domains_file] [max_depth] [max_pages]")
    print("Example: python3 batch_crawler.py domains.txt 4 250")
    print("")
    
    asyncio.run(main())

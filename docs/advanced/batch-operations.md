# Batch Operations

## Overview

The Crawl4AI RAG MCP Server provides powerful batch crawling capabilities for efficiently processing large numbers of URLs. The system includes two utilities:

1. **Batch Crawler** (legacy) - Direct batch crawling from URL files
2. **Recrawl Utility** (modern) - API-based recrawling of existing database URLs with improved architecture

## Batch Crawler

### Location

`/home/robiloo/Documents/mcpragcrawl4ai/core/utilities/batch_crawler.py`

### Features

- **Concurrent Processing**: Configurable number of simultaneous requests (default: 10)
- **Async Architecture**: Built on aiohttp for maximum performance
- **Retry Logic**: Built-in request timeout handling
- **Progress Tracking**: Real-time progress updates every 50 URLs
- **Error Recovery**: Failed URLs logged and saved for reprocessing
- **Performance Metrics**: Tracks crawl rate, success rate, and timing
- **API Integration**: Direct REST API calls for efficient batch processing

## Architecture

```
┌─────────────────────────────────────────┐
│         URLs File (urls.md)             │
│   - One URL per line                    │
│   - Comments with #                     │
│   - Plain text format                   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       BatchCrawler Class                │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  load_urls()                      │  │
│  │  - Read and parse URLs file       │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  run_batch_crawl_async()          │  │
│  │  - Create aiohttp session         │  │
│  │  - Set up semaphore (concurrency) │  │
│  │  - Schedule all tasks             │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  crawl_url_async()                │  │
│  │  - POST to /api/v1/crawl/store    │  │
│  │  - Handle errors and timeouts     │  │
│  │  - Track metrics                  │  │
│  └───────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      REST API Server                    │
│   POST /api/v1/crawl/store              │
│   - Crawl URL                           │
│   - Store in database                   │
│   - Return success/error                │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Results & Metrics                  │
│   - Success/failure counts              │
│   - Failed URLs file                    │
│   - Performance statistics              │
└─────────────────────────────────────────┘
```

## BatchCrawler Class

### Initialization

```python
# From core/utilities/batch_crawler.py
class BatchCrawler:
    def __init__(self, urls_file="urls.md", api_url="http://localhost:8080", api_key=None, max_concurrent=10):
        self.urls_file = urls_file
        self.api_url = api_url
        self.max_concurrent = max_concurrent
        # Try to get API key from env vars
        self.api_key = api_key or os.getenv("LOCAL_API_KEY") or os.getenv("REMOTE_API_KEY") or os.getenv("RAG_API_KEY")

        if not self.api_key:
            print("❌ No API key found!")
            sys.exit(1)

        self.results = []
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
```

### Loading URLs

```python
# From core/utilities/batch_crawler.py
def load_urls(self):
    """Load URLs from urls.md file"""
    if not os.path.exists(self.urls_file):
        print(f"❌ URLs file '{self.urls_file}' not found!")
        return []

    urls = []
    try:
        with open(self.urls_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
                    if line_num <= 10:  # Show first 10
                        print(f"📋 Loaded URL {len(urls)}: {line}")
    except Exception as e:
        print(f"❌ Error reading URLs file: {e}")
        return []

    print(f"\n✅ Loaded {len(urls)} URLs to crawl")
    return urls
```

### Async Crawling

```python
# From core/utilities/batch_crawler.py
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
                    return {'url': url, 'success': True, 'duration': duration, 'error': None}
                else:
                    error = result.get("error", "Unknown error")
                    print(f"[{index}/{total}] ❌ Failed: {error} - {url}")
                    return {'url': url, 'success': False, 'duration': duration, 'error': error}

    except asyncio.TimeoutError:
        end_time = time.time()
        duration = end_time - start_time
        print(f"[{index}/{total}] ⏱️  Timeout after {duration:.1f}s - {url}")
        return {'url': url, 'success': False, 'duration': duration, 'error': 'Request timeout'}

    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"[{index}/{total}] 💥 Exception: {e} - {url}")
        return {'url': url, 'success': False, 'duration': duration, 'error': str(e)}
```

### Concurrency Control

```python
# From core/utilities/batch_crawler.py
async def run_batch_crawl_async(self):
    """Run batch crawl for all URLs with concurrency control"""
    urls = self.load_urls()
    if not urls:
        return

    # Create aiohttp session
    async with aiohttp.ClientSession() as session:
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def bounded_crawl(url: str, index: int, total: int):
            async with semaphore:
                result = await self.crawl_url_async(session, url, index, total)
                self.results.append(result)

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
```

### Summary Statistics

```python
# From core/utilities/batch_crawler.py
def print_summary(self, batch_duration):
    """Print final crawl summary"""
    print("\n" + "="*80)
    print("📊 BATCH CRAWL SUMMARY")
    print("="*80)

    successful = [r for r in self.results if r['success']]
    failed = [r for r in self.results if not r['success']]

    print(f"✅ Successful URLs: {len(successful)}/{len(self.results)}")
    print(f"❌ Failed URLs: {len(failed)}/{len(self.results)}")
    print(f"⏱️  Total duration: {batch_duration/60:.1f} minutes")
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

        # Save failed URLs to file
        failed_file = "failed_urls.txt"
        with open(failed_file, 'w') as f:
            for result in failed:
                f.write(f"{result['url']}\n")
        print(f"\n💾 Failed URLs saved to: {failed_file}")
```

## Usage

### Basic Usage

```bash
# Run with default settings (urls.md, localhost:8080, 10 concurrent)
python3 core/utilities/batch_crawler.py

# Specify custom URL file
python3 core/utilities/batch_crawler.py /path/to/urls.txt

# Specify custom API URL
python3 core/utilities/batch_crawler.py urls.md http://remote-server.com:8080

# Specify custom concurrency level
python3 core/utilities/batch_crawler.py urls.md http://localhost:8080 20
```

### URL File Format

Create a `urls.md` file with one URL per line:

```markdown
# Batch Crawl URLs
# Lines starting with # are comments and will be ignored

https://example.com/page1
https://example.com/page2
https://example.com/page3

# Section 2 - Documentation
https://docs.example.com/intro
https://docs.example.com/guide
https://docs.example.com/api
```

### Environment Variables

The batch crawler automatically detects API keys from environment:

```bash
# In .env file or environment
LOCAL_API_KEY=your-local-api-key-here
REMOTE_API_KEY=your-remote-api-key-here
RAG_API_KEY=fallback-api-key-here
```

### Example Output

```
🤖 Crawl4AI Batch URL Crawler
Usage: python3 batch_crawler.py [urls_file] [api_url] [max_concurrent]

✅ Loaded environment from: /path/to/.env
🔑 Using API key: abc123...
⚡ Max concurrent requests: 10

📋 Loaded URL 1: https://example.com/page1
📋 Loaded URL 2: https://example.com/page2
...

✅ Loaded 100 URLs to crawl

🎬 STARTING BATCH CRAWL
📝 URLs: 100
🌐 API: http://localhost:8080
⚡ Concurrent requests: 10
🕐 Started: 2024-01-15 14:30:00
================================================================================

[1/100] 🔄 Crawling: https://example.com/page1
[2/100] 🔄 Crawling: https://example.com/page2
[1/100] ✅ Success (2.3s) - https://example.com/page1
[2/100] ✅ Success (2.1s) - https://example.com/page2
...

📊 Progress: 50/100 | Success: 48/50 | Rate: 15.2 URLs/min

...

================================================================================
📊 BATCH CRAWL SUMMARY
================================================================================
✅ Successful URLs: 95/100
❌ Failed URLs: 5/100
⏱️  Total duration: 6.8 minutes
📈 Overall rate: 14.7 URLs/minute
⚡ Average crawl time: 2.4 seconds

💥 FAILED URLS (5):
   ❌ https://broken-site.com/page1
      Error: Connection timeout
   ❌ https://another-site.com/missing
      Error: HTTP 404: Not Found
   ...

💾 Failed URLs saved to: failed_urls.txt

🏁 Batch crawl completed at 2024-01-15 14:36:50
```

## Performance Tuning

### Concurrency Level

Adjust based on your system and network capacity:

```bash
# Low concurrency (safer, slower)
python3 core/utilities/batch_crawler.py urls.md http://localhost:8080 5

# Default concurrency (balanced)
python3 core/utilities/batch_crawler.py urls.md http://localhost:8080 10

# High concurrency (faster, more resource intensive)
python3 core/utilities/batch_crawler.py urls.md http://localhost:8080 20

# Very high concurrency (requires good hardware)
python3 core/utilities/batch_crawler.py urls.md http://localhost:8080 50
```

### Recommended Settings

| System Type | RAM | CPU Cores | Recommended Concurrency |
|------------|-----|-----------|------------------------|
| Laptop | 8 GB | 4 | 5-10 |
| Desktop | 16 GB | 8 | 10-20 |
| Server | 32 GB | 16 | 20-50 |
| High-End Server | 64+ GB | 32+ | 50-100 |

### Timeout Configuration

Default timeout is 60 seconds per request. Modify in code if needed:

```python
# In batch_crawler.py
timeout=aiohttp.ClientTimeout(total=60)  # Change to desired timeout
```

## Error Handling

### Common Error Types

1. **Connection Timeout**: Request took longer than 60 seconds
2. **HTTP Errors**: 4xx (client error) or 5xx (server error)
3. **Network Errors**: Connection refused, DNS failure, etc.
4. **API Errors**: Invalid URL, sanitization failure, blocked domain

### Failed URL Recovery

Failed URLs are automatically saved to `failed_urls.txt`:

```bash
# Retry failed URLs
cp failed_urls.txt urls_retry.md
python3 core/utilities/batch_crawler.py urls_retry.md
```

### Retry Strategy

For automatic retry with exponential backoff:

```python
# Custom retry logic (add to batch_crawler.py)
async def crawl_with_retry(self, session, url, max_retries=3):
    for attempt in range(max_retries):
        result = await self.crawl_url_async(session, url, index, total)
        if result['success']:
            return result

        # Exponential backoff
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            await asyncio.sleep(wait_time)

    return result
```

## Database Integration

### Data Flow

```
URLs → Batch Crawler → REST API → RAG System → Database

Each URL:
1. Sent to /api/v1/crawl/store
2. Crawled by Crawl4AI
3. Sanitized and validated
4. Stored in SQLite database
5. Embeddings generated
6. Synced to disk (if RAM mode)
```

### Storage Details

All crawled content is stored with:

- **URL**: Full URL of the page
- **Title**: Page title extracted from HTML
- **Content**: Full page content
- **Markdown**: Converted markdown representation
- **Timestamp**: When the page was crawled
- **Tags**: Automatically tagged with "batch_recrawl"
- **Retention**: Stored permanently by default
- **Embeddings**: 384-dimensional vector embeddings

### Verification

Check crawled content in database:

```bash
# View database stats
python3 core/utilities/dbstats.py

# Or via API
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/stats

# List recently crawled content
curl -H "Authorization: Bearer your-api-key" \
  "http://localhost:8080/api/v1/memory?limit=100"

# Search for batch crawled content
curl -X POST http://localhost:8080/api/v1/search \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "batch_recrawl", "limit": 100}'
```

## Advanced Usage

### Custom Tags

Modify the crawler to use custom tags:

```python
# In batch_crawler.py - crawl_url_async()
json={
    "url": url,
    "retention_policy": "permanent",
    "tags": "my_custom_tag,batch_import_2024"  # Custom tags
}
```

### Remote API

Crawl to a remote server:

```bash
# Set remote API details
export REMOTE_API_KEY=your-remote-api-key
python3 core/utilities/batch_crawler.py urls.md https://remote-server.com:8080 10
```

### Filtered Crawling

Pre-filter URLs before crawling:

```bash
# Extract specific domains
grep "docs.python.org" all_urls.txt > python_docs_urls.md

# Extract by keyword
grep "tutorial" all_urls.txt > tutorial_urls.md

# Crawl filtered set
python3 core/utilities/batch_crawler.py python_docs_urls.md
```

## Monitoring

### Real-Time Monitoring

Watch progress in real-time:

```bash
# In one terminal
python3 core/utilities/batch_crawler.py urls.md

# In another terminal, monitor API
watch -n 5 'curl -s -H "Authorization: Bearer your-api-key" http://localhost:8080/api/v1/stats | jq'
```

### Log Analysis

Check application logs for errors:

```bash
# View recent errors
tail -n 100 data/crawl4ai_rag_errors.log | grep "batch_crawler"

# Monitor logs live
tail -f data/crawl4ai_rag_errors.log
```

## Best Practices

1. **Start Small**: Test with 10-20 URLs before running large batches
2. **Monitor Resources**: Watch CPU, RAM, and network usage
3. **Use Appropriate Concurrency**: Don't overwhelm your system or target servers
4. **Respect Rate Limits**: Consider adding delays for specific domains
5. **Save Failed URLs**: Always review and retry failed URLs
6. **Check Database Stats**: Verify content was stored correctly
7. **Regular Backups**: Backup database before large batch operations
8. **Clean URLs**: Remove duplicates and invalid URLs before batch crawling
9. **Tag Appropriately**: Use descriptive tags for easy filtering later
10. **Document Sources**: Keep notes about where URL lists came from

## Troubleshooting

### Issue: High Memory Usage

**Symptoms**: System running out of memory during batch crawl

**Solutions:**
- Reduce concurrency level
- Process URLs in smaller batches
- Increase system swap space
- Close other applications

### Issue: Slow Crawl Rate

**Symptoms**: Crawl rate is much lower than expected

**Solutions:**
- Check network bandwidth
- Verify Crawl4AI service is healthy
- Increase concurrency if system has capacity
- Check for rate limiting on target sites
- Monitor API server performance

### Issue: Many Timeouts

**Symptoms**: High percentage of timeout errors

**Solutions:**
- Increase timeout duration in code
- Check network connectivity
- Verify target sites are responsive
- Reduce concurrency to lower load
- Check Crawl4AI container logs

### Issue: API Authentication Failures

**Symptoms**: "Unauthorized" errors during batch crawl

**Solutions:**
- Verify API key is correct in environment
- Check .env file is loaded properly
- Restart server after changing API key
- Test API key with single request first

## Database Restoration

If batch crawl is interrupted, you can restore from the last sync point:

```bash
# Check what was successfully stored
python3 core/utilities/dbstats.py

# Compare with crawl progress
# Resume from last successful URL in failed_urls.txt
```

## Integration with Database Stats

View batch crawl results:

```python
# From core/utilities/dbstats.py
python3 core/utilities/dbstats.py

# Output shows:
# - Total pages crawled
# - Recent activity (including batch crawled pages)
# - Storage breakdown
# - Top tags (including "batch_recrawl")
```

## References

- **Implementation**: `/home/robiloo/Documents/mcpragcrawl4ai/core/utilities/batch_crawler.py`
- **Database Stats**: `/home/robiloo/Documents/mcpragcrawl4ai/core/utilities/dbstats.py`
- **REST API**: `/home/robiloo/Documents/mcpragcrawl4ai/api/api.py`
- **Storage Layer**: `/home/robiloo/Documents/mcpragcrawl4ai/core/data/storage.py`

## Recrawl Utility

### Overview

The Recrawl Utility is a modern tool for batch recrawling existing URLs in the database. Unlike the batch crawler which processes URLs from files, this utility:

- Reads URLs directly from the database
- Sends crawl requests via API (avoiding sync conflicts)
- Supports concurrent processing with rate limiting
- Provides dry-run mode for previewing operations
- Filters by retention policy, tags, or URL patterns

### Location

`/home/robiloo/Documents/mcpragcrawl4ai/core/utilities/recrawl_utility.py`

### Key Features

- **API-Based Execution**: Uses `/api/v1/crawl/store` instead of direct database access
- **Concurrent Processing**: Asyncio-based with semaphore rate limiting
- **Database Read**: Reads URLs from disk database (no RAM DB conflicts)
- **Flexible Filtering**: Filter by retention policy, tags, or limit
- **Rate Limiting**: Configurable delay and concurrency
- **Dry-Run Mode**: Preview what will be recrawled before executing
- **Progress Tracking**: Real-time statistics with success/failure counts

### Architecture

```
┌─────────────────────────────────────────┐
│     Disk Database (Direct Read)         │
│   - Reads URLs from crawled_content     │
│   - No RAM DB initialization            │
│   - No sync manager conflicts           │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      RecrawlUtility Class               │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  get_urls_to_recrawl()            │  │
│  │  - Query disk DB directly         │  │
│  │  - Filter by policy/tags          │  │
│  │  - Return URL list                │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  recrawl_batch()                  │  │
│  │  - Concurrent processing          │  │
│  │  - Semaphore rate limiting        │  │
│  │  - Progress tracking              │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  recrawl_url()                    │  │
│  │  - POST to /api/v1/crawl/store    │  │
│  │  - aiohttp async requests         │  │
│  │  - Error handling & retry         │  │
│  └───────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      REST API Server (Docker)           │
│   POST /api/v1/crawl/store              │
│   - Crawl URL via Crawl4AI              │
│   - Clean content (remove navigation)   │
│   - Filter language (English only)      │
│   - Store in RAM DB                     │
│   - Generate embeddings                 │
│   - Sync to disk automatically          │
└─────────────────────────────────────────┘
```

### Usage

#### Basic Usage

```bash
# Activate virtual environment
cd ~/Documents/mcpragcrawl4ai && source .venv/bin/activate

# Dry run to preview all URLs
python3 core/utilities/recrawl_utility.py --all --dry-run

# Recrawl all URLs with default settings (1 concurrent, 1s delay)
python3 core/utilities/recrawl_utility.py --all

# Recrawl with 10 concurrent requests, 0.6s delay (60 req/min)
python3 core/utilities/recrawl_utility.py --all --concurrent 10 --delay 0.6

# Recrawl specific retention policy
python3 core/utilities/recrawl_utility.py --policy permanent --concurrent 5 --delay 1.0

# Recrawl URLs with specific tags
python3 core/utilities/recrawl_utility.py --tags "react,documentation" --limit 100 --concurrent 10 --delay 0.5

# Recrawl single URL
python3 core/utilities/recrawl_utility.py --url https://example.com
```

#### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--url URL` | Recrawl a single URL | None |
| `--all` | Recrawl all URLs in database | False |
| `--policy POLICY` | Filter by retention policy | None |
| `--tags TAGS` | Filter by tags (comma-separated) | None |
| `--limit N` | Maximum URLs to recrawl | None |
| `--delay SECONDS` | Delay between requests | 1.0 |
| `--concurrent N` | Number of concurrent requests | 1 |
| `--dry-run` | Preview without making changes | False |

### Rate Limiting Examples

```bash
# 30 requests per minute (2s delay, 1 concurrent)
python3 core/utilities/recrawl_utility.py --all --concurrent 1 --delay 2.0

# 60 requests per minute (0.6s delay, 10 concurrent)
python3 core/utilities/recrawl_utility.py --all --concurrent 10 --delay 0.6

# 120 requests per minute (0.5s delay, 10 concurrent)
python3 core/utilities/recrawl_utility.py --all --concurrent 10 --delay 0.5

# Conservative (avoid rate limits)
python3 core/utilities/recrawl_utility.py --all --concurrent 5 --delay 1.0
```

### Example Output

```
✅ Loaded environment from /home/user/mcpragcrawl4ai/deployments/server/.env
✅ Adjusted DB_PATH to: ./data/crawl4ai_rag.db
✅ Recrawl utility initialized
   Database: ./data/crawl4ai_rag.db
   API: http://localhost:8080
Fetching URLs from database...
Found 2295 URLs to recrawl

Recrawl 2295 URLs? This will replace content and embeddings. (y/N): y

================================================================================
Recrawl Batch - 2295 URLs
Concurrency: 10 simultaneous requests
Rate limit: 0.6s delay between requests
================================================================================

[1/2295] 🔄 Recrawling: https://react.dev/blog/2025/02/14/sunsetting-create-react-app
✅ Updated: Sunsetting Create React App – React

[2/2295] 🔄 Recrawling: https://react.dev/reference/react/hooks
✅ Updated: Hooks – React

[3/2295] 🔄 Recrawling: https://tanstack.com/query/latest/docs/framework/react/overview
❌ Failed: https://tanstack.com/query/latest/docs/framework/react/overview - HTTP 429

...

================================================================================
Recrawl Statistics
================================================================================
Total URLs: 2295
✅ Success: 2250
❌ Failed: 45
⊘ Skipped: 0

Errors (10):
  • https://example.com/page1
    HTTP 429: Too Many Requests
  • https://example.com/page2
    Non-English content detected: ru
  ...

Success Rate: 98.0%
================================================================================
```

### Content Processing Pipeline

When recrawling, each URL goes through:

1. **API Request**: POST to `/api/v1/crawl/store`
2. **Crawl4AI Extraction**: Uses `fit_markdown` for cleaner content
3. **Content Cleaning**: Removes navigation, boilerplate (70-80% reduction)
4. **Language Detection**: Filters out non-English content
5. **Database Storage**: Replaces old content and embeddings
6. **RAM DB Sync**: Automatically syncs to disk (if RAM mode enabled)

### Filtering Options

#### By Retention Policy

```bash
# Recrawl only permanent content
python3 core/utilities/recrawl_utility.py --policy permanent

# Recrawl only session content
python3 core/utilities/recrawl_utility.py --policy session_only
```

#### By Tags

```bash
# Recrawl React documentation
python3 core/utilities/recrawl_utility.py --tags react

# Recrawl multiple tags
python3 core/utilities/recrawl_utility.py --tags "react,documentation,tutorial"
```

#### By Limit

```bash
# Recrawl first 100 URLs
python3 core/utilities/recrawl_utility.py --all --limit 100

# Test with 10 URLs first
python3 core/utilities/recrawl_utility.py --all --limit 10 --dry-run
```

### Error Handling

#### Common Error Types

1. **HTTP 429 (Too Many Requests)**: Target server rate limiting
   - Solution: Reduce concurrency or increase delay

2. **Non-English Content**: Language detection rejected content
   - This is expected behavior, not an error

3. **Connection Timeout**: Request exceeded 60s
   - Solution: Server may be overloaded, reduce concurrency

4. **HTTP 404/410**: URL no longer exists
   - Solution: Consider removing from database

### Performance Tuning

#### Concurrency Recommendations

| URLs to Recrawl | Recommended Concurrency | Delay |
|-----------------|------------------------|-------|
| < 100 | 1-5 | 1.0s |
| 100-500 | 5-10 | 0.6-1.0s |
| 500-2000 | 10-15 | 0.5-0.6s |
| 2000+ | 10-20 | 0.5-0.6s |

**Note**: Higher concurrency with lower delay may trigger rate limits on target servers.

### Best Practices

1. **Always Dry-Run First**: Preview what will be recrawled
   ```bash
   python3 core/utilities/recrawl_utility.py --all --dry-run
   ```

2. **Start Conservative**: Begin with low concurrency and increase if needed
   ```bash
   python3 core/utilities/recrawl_utility.py --all --concurrent 5 --delay 1.0
   ```

3. **Monitor Progress**: Watch for rate limit errors (HTTP 429)

4. **Filter Before Recrawling**: Use tags/policies to recrawl specific content
   ```bash
   python3 core/utilities/recrawl_utility.py --tags documentation --limit 500
   ```

5. **Check Database Stats**: Verify recrawl success
   ```bash
   python3 core/utilities/dbstats.py
   ```

6. **Docker Must Be Running**: API server must be accessible
   ```bash
   docker compose -f deployments/server/docker-compose.yml ps
   ```

### Advantages Over Batch Crawler

| Feature | Recrawl Utility | Batch Crawler |
|---------|----------------|---------------|
| Source | Database URLs | File URLs |
| Execution | API-based | Direct DB access |
| Sync Conflicts | None | Potential |
| Filtering | Policy/Tags | None |
| Dry-Run | Yes | No |
| Content Processing | Full pipeline | Full pipeline |
| Rate Limiting | Built-in | Manual |
| Use Case | Update existing | Import new |

### Troubleshooting

#### Issue: "no such module: vec0"

**Cause**: Trying to use RAM DB in recrawl utility (old version)

**Solution**: Use latest version that queries disk DB directly and sends to API

#### Issue: High failure rate

**Symptoms**: Many HTTP 429 or timeout errors

**Solutions:**
- Reduce concurrency: `--concurrent 5`
- Increase delay: `--delay 1.5`
- Check API server is running
- Monitor server logs for issues

#### Issue: Non-English content rejected

**Symptoms**: Many "Non-English content detected" errors

**This is expected**: Language filtering is working as designed. These URLs contained non-English content and were intentionally skipped.

### Monitoring

```bash
# Watch recrawl progress in one terminal
python3 core/utilities/recrawl_utility.py --all --concurrent 10 --delay 0.6

# Monitor API server in another terminal
docker logs -f crawl4ai-rag-server

# Check database stats after completion
python3 core/utilities/dbstats.py
```

## See Also

- [Database Statistics](../guides/troubleshooting.md#database-issues)
- [API Endpoints](../api/endpoints.md)
- [Performance Optimization](../guides/deployment.md#performance-considerations)
- [RAM Database Mode](ram-database.md)
- [Content Cleaning Pipeline](../guides/content-processing.md)
